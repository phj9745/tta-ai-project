# backend/services/google/metadata.py
# -------------------------------------------------------
# GPT 기반 시험 합의서 메타데이터 추출 (드롭인 교체판)
# -------------------------------------------------------
from __future__ import annotations

import io
import os
import re
import json
from typing import Dict, List, Optional

from fastapi import HTTPException
from docx import Document
from pypdf import PdfReader

from anthropic import Anthropic, AnthropicError

# --- 외부로 노출되는 정규식(기존 코드와 동일한 인터페이스) ---
# 공백/대시 삽입 변형 허용 (예: "G S - B - 12 - 3456")
EXAM_NUMBER_PATTERN = re.compile(
    r"G\s*S\s*-\s*[A-Z]\s*-\s*\d{2}\s*-\s*\d{4}",
    re.IGNORECASE,
)

# --- 내부 상수 ---
_MAXLEN = 160


# =========================
# 공개 API
# =========================
def build_project_folder_name(metadata: Dict[str, str]) -> str:
    """폴더명: [시험번호] 회사명 - 제품명및버전(영문 우선). 슬래시는 전각으로 치환."""
    def _one_line(s: str, n: int = _MAXLEN) -> str:
        import re as _re
        return _re.sub(r"\s+", " ", (s or "").strip())[:n]

    def _is_ascii_dominant(s: str) -> bool:
        if not s:
            return False
        a = sum(1 for ch in s if ord(ch) < 128)
        return a >= max(1, len(s) // 2)

    exam_number = _one_line(metadata.get("exam_number", ""))
    company_name = _one_line(metadata.get("company_name", ""))
    product_name_version = (
        _one_line(metadata.get("product_name_version", ""))
        or _one_line(metadata.get("product_name_en", ""))
        or _one_line(metadata.get("product_name", ""))
    )

    preferred = metadata.get("product_name_en") or metadata.get("product_name") or product_name_version
    if preferred and _is_ascii_dominant(preferred):
        product_name_version = preferred

    safe = (product_name_version or "").replace("/", "／").replace("\\", "＼")
    return f"[{exam_number}] {company_name} - {safe}".strip()


def extract_project_metadata(
    file_bytes: bytes,
    *,
    file_extension: Optional[str] = None,   # ".pdf" | ".docx"
    pdf_engine: str = "pypdf",              # "pypdf" | "pdfminer" | "ocr"
    filename_hint: Optional[str] = None,    # 파일명에서 시험번호 보조 추출
) -> Dict[str, str]:
    """
    DOCX/PDF에서 텍스트를 추출 후, GPT로 메타데이터 추출.
    반환 키(기존 필드명 유지):
      - exam_number (필수)
      - company_name (필수)
      - product_name / product_name_en (둘 중 하나)
      - product_name_version (폴더명에 사용)
    """
    text = _extract_text(file_bytes, file_extension, pdf_engine)
    if not text.strip():
        raise HTTPException(status_code=422, detail="문서에서 텍스트를 추출하지 못했습니다.")

    data = _call_anthropic_structured(text)

    # 정규화 & 보정
    exam = _tighten_exam_number(data.get("exam_number", ""))
    if not exam:
        exam = _tighten_exam_number(text)
    if not exam and filename_hint:
        exam = _tighten_exam_number(filename_hint)

    comp = _clean_company(data.get("company_name", ""))

    pn_ko = _one_line(data.get("product_name_ko", ""))
    pn_en = _one_line(data.get("product_name_en", ""))
    ver   = _one_line(data.get("product_version_hint", ""))

    product_name_version = _choose_product_name_version(pn_ko, pn_en, ver)
    product_name_compat  = pn_ko or pn_en

    meta = {
        "exam_number": exam,
        "company_name": comp,
        "product_name": product_name_compat,     # 기존 코드 호환
        "product_name_en": pn_en,
        "product_name_version": product_name_version,
    }
    _validate(meta)
    return meta


# =========================
# 내부 구현부
# =========================
def _one_line(s: str, n: int = _MAXLEN) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())[:n]


def _tighten_exam_number(s: str) -> str:
    m = EXAM_NUMBER_PATTERN.search(s or "")
    return re.sub(r"\s+", "", m.group(0).upper()) if m else ""


def _clean_company(s: str) -> str:
    s = _one_line(s, 80)
    s = re.sub(r"^(제조자|제조사|업체명?|회사|회사명|제조업체)\s*[:：]?\s*", "", s)
    s = re.sub(r"\s*\([^)]*\)\s*$", "", s)
    return s.strip()


def _is_ascii_dominant(s: str) -> bool:
    if not s:
        return False
    ascii_count = sum(1 for ch in s if ord(ch) < 128)
    return ascii_count >= max(1, len(s) // 2)


def _choose_product_name_version(ko: str, en: str, version_hint: str) -> str:
    base = en if en and _is_ascii_dominant(en) else (en or ko)
    if version_hint and (base or "") and version_hint not in base:
        return _one_line(f"{base} {version_hint}")
    return _one_line(base)


def _validate(meta: Dict[str, str]) -> None:
    if not meta.get("exam_number"):
        raise HTTPException(status_code=422, detail="시험신청 번호를 찾을 수 없습니다.")
    if not meta.get("company_name"):
        raise HTTPException(status_code=422, detail="제조자(업체명)를 찾을 수 없습니다.")
    if not (meta.get("product_name") or meta.get("product_name_en")):
        raise HTTPException(status_code=422, detail="제품명 및 버전을 찾을 수 없습니다.")


# -------- 텍스트 추출 --------
def _extract_text(file_bytes: bytes, file_extension: Optional[str], pdf_engine: str) -> str:
    ext = (file_extension or "").lower().lstrip(".")
    if ext == "docx":
        return _from_docx(file_bytes)
    if ext == "pdf":
        return _from_pdf(file_bytes, engine=pdf_engine)
    # 확장자 미지정: DOCX→실패 시 PDF
    try:
        return _from_docx(file_bytes)
    except Exception:
        return _from_pdf(file_bytes, engine=pdf_engine)


def _from_docx(b: bytes) -> str:
    try:
        doc = Document(io.BytesIO(b))
    except Exception as exc:  # pragma: no cover
        raise HTTPException(status_code=422, detail="DOCX 파일을 읽지 못했습니다.") from exc
    lines: List[str] = []
    for t in doc.tables:
        for r in t.rows:
            for c in r.cells:
                if c and c.text:
                    lines.append(_one_line(c.text))
    for p in doc.paragraphs:
        if p.text:
            lines.append(_one_line(p.text))
    return "\n".join(ln for ln in lines if ln)


def _from_pdf(b: bytes, *, engine: str) -> str:
    engine = (engine or "pypdf").lower().strip()
    if engine == "pypdf":
        try:
            reader = PdfReader(io.BytesIO(b))
        except Exception as exc:  # pragma: no cover
            raise HTTPException(status_code=422, detail="PDF 파일을 읽지 못했습니다.") from exc
        lines: List[str] = []
        for p in reader.pages:
            try:
                text = p.extract_text() or ""
            except Exception as exc:  # pragma: no cover
                raise HTTPException(status_code=422, detail="PDF 텍스트 추출 실패.") from exc
            for ln in text.splitlines():
                ln = _strip_ctrl_spaces(ln)
                if ln and not _likely_header_footer(ln):
                    lines.append(ln)
        return "\n".join(lines)

    if engine == "pdfminer":
        try:
            from pdfminer.high_level import extract_text  # type: ignore
        except Exception:
            raise HTTPException(status_code=501, detail="pdfminer가 설치되어 있지 않습니다.")
        text = extract_text(io.BytesIO(b)) or ""
        return "\n".join(
            _strip_ctrl_spaces(ln) for ln in text.splitlines()
            if ln and not _likely_header_footer(ln)
        )

    if engine == "ocr":
        try:
            import pytesseract  # type: ignore
            from pdf2image import convert_from_bytes  # type: ignore
        except Exception:
            raise HTTPException(status_code=501, detail="OCR 모드에 pytesseract/pdf2image가 필요합니다.")
        images = convert_from_bytes(b, dpi=300)
        lines: List[str] = []
        for img in images:
            ocr = pytesseract.image_to_string(img, lang="kor+eng") or ""
            lines.extend(
                _strip_ctrl_spaces(ln) for ln in ocr.splitlines()
                if ln and not _likely_header_footer(ln)
            )
        return "\n".join(lines)

    raise HTTPException(status_code=400, detail="지원하지 않는 PDF 파서 엔진입니다.")


def _strip_ctrl_spaces(line: str) -> str:
    if not line:
        return ""
    line = "".join(ch for ch in line if ch.isprintable() or ch in "\t ")
    line = re.sub(r"[\u2000-\u200B\u202F\u205F\u3000]", " ", line)  # 제로폭/넓은 공백 제거
    return line.strip()


def _likely_header_footer(ln: str) -> bool:
    if not ln:
        return True
    if re.fullmatch(r"-{3,}|_{3,}|〔?\d+/?\d+〕?", ln):  # 구분선/페이지번호류
        return True
    return False


# =========================
# GPT 호출부 (이중 폴백)
# =========================
_SYS = (
    "당신은 문서에서 프로젝트 생성용 메타데이터를 추출하는 전문가입니다.\n"
    "- 시험신청번호는 'GS-B-12-3456' 패턴만 허용(공백/대시 포함 가능).\n"
    "- 회사명은 고유명(문장형 설명 금지).\n"
    "- 제품명은 국문/영문을 각각. 없으면 빈 문자열.\n"
    "- 버전은 명확할 때만 product_version_hint에.\n"
    "- 반드시 JSON만 출력.\n"
)

_JSON_KEYS = [
    "exam_number",
    "company_name",
    "product_name_ko",
    "product_name_en",
    "product_version_hint",
    "evidence",
    "confidence",
]


def _get_anthropic_client() -> Anthropic:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY가 설정되어 있지 않습니다.")
    return Anthropic(api_key=api_key)


def _extract_json_safely(s: str) -> dict:
    """코드펜스/앞뒤 설명이 섞여도 JSON만 최대한 안전 추출."""
    if not s:
        return {}
    try:
        return json.loads(s)
    except Exception:
        pass

    # fenced code block 우선
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.DOTALL | re.IGNORECASE)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass

    # 첫 번째 top-level {..}만 추출 (중첩 안전 흉내)
    # 균형 맞는 중괄호를 선형으로 스캔
    start = s.find("{")
    while start != -1:
        depth = 0
        for end in range(start, len(s)):
            ch = s[end]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    chunk = s[start : end + 1]
                    try:
                        return json.loads(chunk)
                    except Exception:
                        break
        start = s.find("{", start + 1)

    return {}


def _ensure_shape(d: dict) -> dict:
    """필요 키를 보장하고 타입을 정리(없으면 기본값)."""
    out = {
        "exam_number": str(d.get("exam_number") or "").strip(),
        "company_name": str(d.get("company_name") or "").strip(),
        "product_name_ko": str(d.get("product_name_ko") or "").strip(),
        "product_name_en": str(d.get("product_name_en") or "").strip(),
        "product_version_hint": str(d.get("product_version_hint") or "").strip(),
        "evidence": [],
        "confidence": float(d.get("confidence") or 0.0),
    }
    ev = d.get("evidence")
    if isinstance(ev, list):
        out["evidence"] = [str(x) for x in ev if isinstance(x, (str, int, float))][:3]
    return out


def _call_anthropic_structured(text: str) -> Dict:
    """Anthropic Messages API를 사용하여 구조화된 데이터 추출."""
    client = _get_anthropic_client()
    model = os.getenv("AI_MODEL", "claude-haiku-4-5-20251001")

    sys_prompt = _SYS
    user_prompt = (
        "다음 텍스트에서 메타데이터를 JSON으로만 반환하세요.\n"
        f"- 키: {', '.join(_JSON_KEYS)}\n"
        "- evidence는 원문에서 발췌한 1~3줄 배열, confidence는 0~1 부동소수점\n\n"
        f"{text[:150_000]}"
    )

    try:
        resp = client.messages.create(
            model=model,
            system=sys_prompt,
            messages=[
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=1000,
            temperature=0.0,
        )

        content = ""
        if resp.content and len(resp.content) > 0:
             content = resp.content[0].text

        data = _extract_json_safely(content)
        if data:
            return _ensure_shape(data)

        raise RuntimeError("모델 응답에서 JSON을 파싱하지 못했습니다.")
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Anthropic 추출 실패: {e}")
