# 🧪 TestMate

TestMate는 Google Drive 기반 프로젝트 자료를 활용해 기능 정의서, 테스트케이스, 결함·보안·성능 리포트까지 한 번에 만들어 주는 AI 업무 자동화 허브입니다. 반복적인 문서화 작업을 줄이고, 운영자가 직접 프롬프트와 템플릿을 다듬어 조직 맞춤형 산출물을 얻을 수 있도록 설계되었습니다.

---

## 📚 목차
- [핵심 가치](#핵심-가치)
- [주요 기능](#주요-기능)
- [시스템 구성](#시스템-구성)
- [시작하기](#시작하기)
  - [사전 준비](#사전-준비)
  - [환경 변수 설정](#환경-변수-설정)
  - [실행 방법](#실행-방법)
- [테스트](#테스트)
- [프로젝트 구조](#프로젝트-구조)
- [프롬프트 및 템플릿 관리 팁](#프롬프트-및-템플릿-관리-팁)

---

<a id="핵심-가치"></a>
## 💡 핵심 가치
- **현업 친화성**: 기존 Google Drive 워크플로를 그대로 사용하면서 AI 생성 기능만 덧붙여, 추가 도구 학습 없이 빠르게 도입할 수 있습니다.
- **품질 통제력**: 관리자 페이지에서 프롬프트, 첨부 설명 템플릿, 내장 컨텍스트를 직접 조정해 조직별 산출물 품질을 통제할 수 있습니다.
- **확장 가능성**: React + FastAPI + OpenAI Responses API로 구성된 모듈형 아키텍처를 사용해 새로운 문서 유형과 외부 연동을 쉽게 추가할 수 있습니다.

---

<a id="주요-기능"></a>
## 🚀 주요 기능
### 1. Google Drive 프로젝트 허브
- 로그인 후 Drive 루트 폴더 상태를 점검하고, 필요한 경우 자동으로 생성합니다.
- 기존 프로젝트 폴더를 한눈에 확인하고, 새 프로젝트를 생성하거나 삭제할 수 있습니다.
- 오류 발생 시 다시 시도, 상세 메시지 확인, 성공 알림 등을 제공해 운영자가 즉시 대응할 수 있습니다.

### 2. 문서 생성 & 편집 워크플로
프로젝트 관리 페이지에서 아래 메뉴를 전환하며 모든 문서 작업을 수행합니다.

| 메뉴 | 설명 |
| --- | --- |
| **형상 이미지 추출** | 시연 동영상을 업로드하면 장면 전환을 감지해 주요 화면 이미지를 자동 추출합니다. |
| **기능리스트 생성** | 요구사항 문서를 분석해 기능 대·중·소 분류와 근거 자료가 포함된 CSV를 생성합니다. |
| **테스트케이스 생성/보정** | 기능리스트 기반 테스트 시나리오를 생성하고, 행별 수정, 최종 확정, XLSX 내보내기까지 한 화면에서 지원합니다. |
| **결함 리포트** | 결함 요약을 CSV로 생성하고, 확정된 행을 Google 스프레드시트에 직접 반영할 수 있습니다. |
| **보안성 리포트** | 사전 정의된 보안 점검 항목과 첨부 자료를 활용해 자동으로 리포트를 작성합니다. |
| **성능 리포트** | 성능 측정 로그와 OS 정보를 업로드하면 자동 요약과 권장 사항을 정리합니다. |

공통 기능으로는 파일 확장자 제한, 필수 문서 검증, 업로드 진행 표시, AI 호출 중단(AbortController) 처리, CSV/XLSX 다운로드, 상태 메시지/경고 표시 등이 포함됩니다.

### 3. 관리자 프롬프트 스튜디오
- 프롬프트 카테고리별로 시스템/사용자 프롬프트, 평가 기준, 모델 파라미터를 편집하고 기본값으로 복원할 수 있습니다.
- 첨부 설명 템플릿과 안내 문구를 커스터마이징해 AI가 파일 맥락을 이해하도록 돕습니다.
- 내장 컨텍스트(XLSX, PDF 등)를 업로드하여 모든 생성 요청에 기본 자료를 포함시킬 수 있습니다.
- 최근 요청 로그를 확인해 문제 상황을 진단하고, 프롬프트 변경 효과를 빠르게 검증합니다.

---

<a id="시스템-구성"></a>
## 🏗️ 시스템 구성
```
frontend/ (React + Vite)
  ├─ pages/ (로그인, Drive 설정, 프로젝트 관리, 프롬프트 관리자)
  ├─ components/ (파일 업로드, 워크플로, 레이아웃 컴포넌트)
  └─ app/ (라우팅, 인증 상태, 백그라운드 작업 컨텍스트)

backend/ (FastAPI)
  ├─ routes/ (auth, drive, prompts API)
  ├─ services/
  │    ├─ google_drive/ (폴더 관리, 시트 업데이트, 파일 변환)
  │    ├─ ai_generation/ (OpenAI Responses API 요청, CSV/XLSX 작성)
  │    ├─ security_report/, performance_report/ (특화 리포트 생성)
  │    └─ prompt_config/ (프롬프트 저장소, 내장 컨텍스트 로딩)
  ├─ template/ (기본 제공 문서 템플릿)
  └─ app/config.py (환경 변수 로딩, 토큰 저장 경로 설정)
```

### 외부 연동
- **Google OAuth 2.0 & Drive API**: 프로젝트 폴더 생성/삭제, 시트 업데이트, 파일 추출을 담당합니다.
- **OpenAI Responses API**: 기능리스트, 테스트케이스, 각종 리포트 생성을 위한 핵심 언어 모델을 호출합니다.
- **CSV/XLSX 처리**: `pandas`, `openpyxl`, `xlrd` 등을 사용해 생성 결과를 표준 문서 형식으로 제공합니다.

---

<a id="시작하기"></a>
## 🔧 시작하기
### 사전 준비
- Python 3.12+
- Node.js 20+
- Google Cloud에서 발급한 OAuth 클라이언트 (Drive API 권한 필요)
- OpenAI API 키 (Responses API 지원 모델)

### 환경 변수 설정
1. `backend/.env` 파일을 생성하고 아래 예시를 참고해 값을 입력하세요.
   ```env
   GOOGLE_CLIENT_ID=your-google-oauth-client-id
   GOOGLE_CLIENT_SECRET=your-google-oauth-client-secret
   GOOGLE_REDIRECT_URI=https://your.backend.host/auth/google/callback
   FRONTEND_REDIRECT_URL=http://localhost:5173/auth/callback
   OPENAI_API_KEY=sk-...
   OPENAI_MODEL=gpt-5-mini
   # 선택 사항
   GOOGLE_TOKEN_DB_PATH=/workspace/tta-ai-project/backend/app/google_tokens.db
   BUILTIN_TEMPLATE_ROOT=/workspace/tta-ai-project/backend/template
   ```
   > `GOOGLE_TOKEN_DB_PATH`를 지정하지 않으면 `backend/app/google_tokens.db`가 사용됩니다. 프롬프트 설정은 같은 폴더의 `prompt_configs.json`에 저장됩니다.

2. 프런트엔드에서 사용할 백엔드 주소가 기본값(`http://localhost:8000`)과 다르면 `frontend/.env` 파일에 아래 항목을 추가합니다.
   ```env
   VITE_BACKEND_URL=https://your.backend.host
   ```

### 실행 방법
#### 1) Docker Compose (권장)
```bash
# 저장소 클론 후 최상위 디렉터리에서 실행
docker compose up --build
```
- 프런트엔드: http://localhost:5173
- 백엔드: http://localhost:8000

#### 2) 로컬 개발 환경
1. **백엔드**
   ```bash
   cd backend
   python -m venv .venv
   source .venv/bin/activate  # Windows는 .venv\Scripts\activate
   pip install -r requirements.txt
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
2. **프런트엔드**
   ```bash
   cd frontend
   npm install
   npm run dev -- --host 0.0.0.0 --port 5173
   ```

> Google OAuth Redirect URI에는 `https://<backend-host>/auth/google/callback`이 등록되어 있어야 합니다. 로컬 개발 시에는 `http://localhost:8000/auth/google/callback`을 허용하세요.

---

<a id="테스트"></a>
## ✅ 테스트
- **백엔드**: `cd backend && pytest`
- **프런트엔드**: `cd frontend && npm run test`

---

<a id="프로젝트-구조"></a>
## 🗂️ 프로젝트 구조
```
tta-ai-project/
├─ README.md
├─ docker-compose.yml
├─ backend/
│  ├─ app/
│  │  ├─ routes/
│  │  ├─ services/
│  │  ├─ dependencies.py
│  │  ├─ config.py
│  │  └─ main.py
│  ├─ template/
│  ├─ tests/
│  ├─ requirements.txt
│  └─ Dockerfile
└─ frontend/
   ├─ src/
   │  ├─ pages/
   │  ├─ components/
   │  ├─ app/
   │  └─ config.ts
   ├─ public/
   ├─ package.json
   └─ Dockerfile
```

---

<a id="프롬프트-및-템플릿-관리-팁"></a>
## 🧾 프롬프트 및 템플릿 관리 팁
- **첨부 설명 템플릿 키**: `{{index}}`, `{{descriptor}}`, `{{label}}`, `{{description}}`, `{{extension}}`, `{{doc_id}}`, `{{notes}}`, `{{source_path}}`, `{{context_summary}}` 등을 조합해 파일 목록을 원하는 형식으로 렌더링할 수 있습니다.
- **내장 컨텍스트**: `backend/template` 아래에 배치하면 관리자 페이지에서 추가/삭제 여부를 제어할 수 있으며, `BUILTIN_TEMPLATE_ROOT` 환경 변수를 통해 다른 경로도 지정할 수 있습니다.
- **요청 로그**: `prompt_requests.log` 파일에 최근 프롬프트 호출 내역이 저장됩니다. 생성 품질이나 오류를 분석할 때 유용합니다.
- **Google 토큰 저장소**: 다수의 계정을 운용할 경우 `backend/app/google_tokens.db` 파일을 백업해두면 재인증 과정을 줄일 수 있습니다.

---

TestMate는 반복 문서 업무를 자동화하면서도 운영자가 품질을 직접 제어할 수 있는 실용적인 AI 파트너입니다. 새로운 문서 유형이나 외부 연동 아이디어가 있다면 `docs/COLLABORATION_GUIDE.md`를 참고해 함께 발전시켜 주세요!
