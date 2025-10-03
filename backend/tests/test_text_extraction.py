from __future__ import annotations

import base64
import unittest
from pathlib import Path
import io
import zipfile
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.services.text_extraction import extract_text_preview


def _build_sample_xlsx() -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">
  <Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>
  <Default Extension=\"xml\" ContentType=\"application/xml\"/>
  <Override PartName=\"/xl/workbook.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml\"/>
  <Override PartName=\"/xl/worksheets/sheet1.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml\"/>
  <Override PartName=\"/xl/sharedStrings.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.spreadsheetml.sharedStrings+xml\"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"xl/workbook.xml\"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet\" Target=\"worksheets/sheet1.xml\"/>
  <Relationship Id=\"rId2\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/sharedStrings\" Target=\"sharedStrings.xml\"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<workbook xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" xmlns:r=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships\">
  <sheets>
    <sheet name=\"기능목록\" sheetId=\"1\" r:id=\"rId1\"/>
  </sheets>
</workbook>""",
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<sst xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\" count=\"6\" uniqueCount=\"6\">
  <si><t>기능 ID</t></si>
  <si><t>기능명</t></si>
  <si><t>설명</t></si>
  <si><t>FT-001</t></si>
  <si><t>로그인</t></si>
  <si><t>사용자 인증</t></si>
</sst>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            """<?xml version=\"1.0\" encoding=\"UTF-8\" standalone=\"yes\"?>
<worksheet xmlns=\"http://schemas.openxmlformats.org/spreadsheetml/2006/main\">
  <sheetData>
    <row r=\"1\">
      <c r=\"A1\" t=\"s\"><v>0</v></c>
      <c r=\"B1\" t=\"s\"><v>1</v></c>
      <c r=\"C1\" t=\"s\"><v>2</v></c>
    </row>
    <row r=\"2\">
      <c r=\"A2\" t=\"s\"><v>3</v></c>
      <c r=\"B2\" t=\"s\"><v>4</v></c>
      <c r=\"C2\" t=\"s\"><v>5</v></c>
    </row>
  </sheetData>
</worksheet>""",
        )
    return output.getvalue()


class TextExtractionTests(unittest.TestCase):
    def test_extract_pdf_text(self) -> None:
        pdf_base64 = (
            "JVBERi0xLjQKJeLjz9MKMSAwIG9iago8PAovVHlwZSAvQ2F0YWxvZwovUGFnZXMgMiAwIFIKPj4KZW5k"
            "b2JqCjIgMCBvYmoKPDwKL1R5cGUgL1BhZ2VzCi9LaWRzIFszIDAgUl0KL0NvdW50IDEKPj4KZW5kb2Jq"
            "CjMgMCBvYmoKPDwKL1R5cGUgL1BhZ2UKL1BhcmVudCAyIDAgUgovTWVkaWFCb3ggWzAgMCAyMDAgMjAw"
            "XQovQ29udGVudHMgNCAwIFIKL1Jlc291cmNlcyA8PAovRm9udCA8PAovRjEgNSAwIFIKPj4KPj4KPj4K"
            "ZW5kb2JqCjQgMCBvYmoKPDwKL0xlbmd0aCA0NAo+PnN0cmVhbQpCVAovRjEgMjQgVGYKNTAgMTUwIFRk"
            "CihIZWxsbyBQREYpIFRqCkVUCmVuZHN0cmVhbQplbmRvYmoKNSAwIG9iago8PAovVHlwZSAvRm9udAov"
            "U3VidHlwZSAvVHlwZTEKL0Jhc2VGb250IC9IZWx2ZXRpY2EKPj4KZW5kb2JqCnhyZWYKMCA2CjAwMDAw"
            "MDAwMCA2NTUzNSBmIAowMDAwMDAwMTAgMDAwMDAgbiAKMDAwMDAwMDcxIDAwMDAwIG4gCjAwMDAwMDE2"
            "NCAwMDAwMCBuIAowMDAwMDAyNTUgMDAwMDAgbiAKMDAwMDAwMzU4IDAwMDAwIG4gCnRyYWlsZXIKPDwK"
            "L1Jvb3QgMSAwIFIKL1NpemUgNgovSW5mbyA3IDAgUgo+PgpzdGFydHhyZWYKNDc2CiUlRU9G"
        )
        pdf_bytes = base64.b64decode(pdf_base64)
        preview = extract_text_preview(
            filename="sample.pdf",
            raw=pdf_bytes,
            content_type="application/pdf",
            max_chars=2000,
        )
        self.assertIn("Hello PDF", preview.body)

    def test_extract_html_text(self) -> None:
        html_bytes = "<html><body><h1>제목</h1><p>본문 내용입니다.</p></body></html>".encode("utf-8")
        preview = extract_text_preview(
            filename="sample.html",
            raw=html_bytes,
            content_type="text/html",
            max_chars=500,
        )
        self.assertIn("제목", preview.body)
        self.assertIn("본문 내용입니다.", preview.body)

    def test_extract_image_fallback(self) -> None:
        image_bytes = b"\xff\xd8\xff"  # JPEG header bytes
        preview = extract_text_preview(
            filename="image.jpg",
            raw=image_bytes,
            content_type="image/jpeg",
            max_chars=500,
        )
        self.assertIn("이미지에서 텍스트를 추출할 수 없습니다", preview.body)

    def test_extract_xlsx_text(self) -> None:
        xlsx_bytes = _build_sample_xlsx()
        preview = extract_text_preview(
            filename="features.xlsx",
            raw=xlsx_bytes,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            max_chars=2000,
        )
        self.assertIn("기능 ID | 기능명 | 설명", preview.body)
        self.assertIn("FT-001 | 로그인 | 사용자 인증", preview.body)

    def test_extract_without_limit(self) -> None:
        body = "문단1" + "\n" * 2 + "문단2" * 2000
        preview = extract_text_preview(
            filename="manual.txt",
            raw=body.encode("utf-8"),
            content_type="text/plain",
            max_chars=0,
        )
        self.assertTrue(preview.body.endswith("문단2"))
        self.assertGreater(len(preview.body), 5000)


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
