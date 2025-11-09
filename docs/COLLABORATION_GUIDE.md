# 🤝 TestMate 협업 가이드

> 새 팀원이 빠르게 전체 구조와 핵심 개념을 파악할 수 있도록 정리한 온보딩 문서입니다. 기존 `README.md`와 별도로 유지합니다.

## 1. 시스템 구성 요약

- **Frontend**: React + TypeScript + Vite 기반 단일 페이지 애플리케이션. `App.tsx`에서 인증 상태와 경로에 따라 페이지를 렌더링하며 상단 `AppShell`을 통해 드라이브/프롬프트/로그아웃 액션을 제공합니다.【F:frontend/src/App.tsx†L1-L37】
- **Backend**: FastAPI. `create_app()`에서 CORS 설정 및 라우터를 묶고, 의존성 컨테이너를 `app.state.container`에 보관합니다.【F:backend/app/application.py†L1-L38】
- **데이터/외부 연동**: Google OAuth & Drive, OpenAI Responses API. 환경변수는 `Settings` 데이터클래스로 로드하며 토큰/프롬프트 파일 경로도 여기서 설정합니다.【F:backend/app/config.py†L1-L46】【F:backend/app/container.py†L1-L57】

## 2. 주요 디렉터리 맵

```
root
├── backend/            # FastAPI 서비스
│   ├── app/            # 애플리케이션 코드
│   │   ├── routes/     # REST 엔드포인트 정의
│   │   ├── services/   # Drive, OAuth, 프롬프트, AI 호출 로직
│   │   └── container.py # 서비스 인스턴스 생성/DI
│   ├── template/       # 표준 Excel/문서 템플릿
│   └── tests/          # FastAPI 유닛/통합 테스트
├── frontend/           # React 앱
│   ├── src/            # TSX/TS 소스
│   │   ├── app/        # 공용 레이아웃, 훅, 라우팅 로직
│   │   ├── components/ # 도메인별 UI 컴포넌트
│   │   └── pages/      # 실제 페이지 엔트리
└── docker-compose.yml  # 프론트/백엔드 동시 개발 환경
```

## 3. 환경 변수 및 비밀 관리

| 변수 | 설명 | 위치 |
| --- | --- | --- |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | Google OAuth 인증 정보 | `backend/app/config.py` | 
| `FRONTEND_REDIRECT_URL` | 로그인 이후 리다이렉트 경로(CORS 기준) | `backend/app/config.py` |
| `GOOGLE_TOKEN_DB_PATH` | 발급 토큰 SQLite/JSON 경로 | `backend/app/config.py` |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | OpenAI Responses API 설정 | `backend/app/config.py` |
| `BUILTIN_TEMPLATE_ROOT` | 내장 프롬프트/템플릿 커스텀 루트 (선택) | `backend/app/config.py` |

- 기본값은 `.env` 없이도 동작하도록 정의되어 있지만, 실제 환경에서는 `backend/.env` 파일(또는 배포 비밀)에 위 항목을 채워야 합니다.
- Google OAuth 토큰은 `TokenStorage`가 `tokens_path` 위치에 저장하므로, 로컬 개발 시 `.gitignore`에 포함된지 확인합니다.【F:backend/app/container.py†L17-L24】

## 4. 로컬 개발 워크플로우

### 4.1 Docker Compose (권장)
1. `docker compose up --build`
2. 프론트엔드: http://localhost:5173
3. 백엔드: http://localhost:8000/docs (자동 리로드)
4. `.env`는 `backend/.env`를 참고하여 작성

### 4.2 개별 실행
- **Backend**
  ```bash
  cd backend
  python -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  uvicorn app.main:app --reload
  ```
- **Frontend**
  ```bash
  cd frontend
  npm install
  npm run dev -- --host 0.0.0.0 --port 5173
  ```
- 프론트 개발 시 `VITE_API_BASE_URL` 환경 변수를 `.env.local` 등에 지정하면 API 엔드포인트를 맞출 수 있습니다.

## 5. 핵심 도메인 로직 이해 포인트

### 5.1 Drive & 프로젝트 관리
- `/drive/gs/setup`, `/drive/projects` 등 주요 엔드포인트는 `backend/app/routes/drive.py`에 정의되어 있습니다.
- `_REQUIRED_MENU_DOCUMENTS` 매핑으로 메뉴별 필수 첨부 문서를 제한하며, 업로드 파일 확장자 검증도 수행합니다.【F:backend/app/routes/drive.py†L1-L88】
- 엑셀 출력은 `services/excel_templates` 하위 모듈에서 처리하며, 표준 양식(`template/`)을 로드해 채워 넣습니다.【F:backend/app/routes/drive.py†L89-L113】

### 5.2 프롬프트 관리 & AI 호출
- `AIGenerationService`는 OpenAI API 호출과 프롬프트 구성/로그 기록을 담당합니다.【F:backend/app/container.py†L25-L57】
- 관리자 화면에서 저장한 프롬프트 설정은 `PromptConfigService`가 `prompt_configs.json`으로 직렬화합니다.【F:backend/app/container.py†L19-L29】
- 최근 요청 로그는 `PromptRequestLogService`가 `prompt_requests.log` 파일에 Append 합니다.【F:backend/app/container.py†L27-L35】

### 5.3 프론트엔드 라우팅 & 상태 관리
- `useAuthStatus`, `useRouteGuards`, `resolvePage` 조합으로 로그인 여부에 따른 페이지 가드를 구현합니다.【F:frontend/src/App.tsx†L4-L20】
- 상단 `AppShell`은 공통 네비게이션과 핸들러(`openGoogleDriveWorkspace`, `clearAuthentication`, 관리자 이동)를 props로 받아 동작합니다.【F:frontend/src/App.tsx†L1-L37】
- Google OAuth 토큰/프로젝트 정보는 `localStorage` 기반 유틸(`frontend/src/auth.ts`, `frontend/src/drive.ts`)을 통해 관리합니다.

## 6. 생성 메뉴별 파일 가이드

각 생성 메뉴는 프론트엔드 업로드 UI, 백엔드 생성/스프레드시트 반영 라우터, 그리고 관리자 프롬프트 설정으로 구성되어 있습니다. 변경 시 아래 파일을 함께 확인하세요.

- **기능리스트 생성 (`feature-list`)**
  - 프론트엔드: `ProjectManagementPage`에서 메뉴 정의·필수 문서를 구성합니다.【F:frontend/src/pages/ProjectManagementPage.tsx†L9-L155】
  - 백엔드: `/drive/projects/{project_id}/generate` 라우트가 필수 문서 검증과 스프레드시트 업데이트를 처리하며, 기능리스트 전용 조회/수정 API도 제공합니다.【F:backend/app/routes/drive.py†L241-L401】【F:backend/app/routes/drive.py†L499-L566】
  - 프롬프트 관리자: 기본 프롬프트는 `PromptConfigService`의 `feature-list` 엔트리로 정의되고, 관리자 화면에서 동일 ID로 노출됩니다.【F:backend/app/services/prompt_config.py†L136-L194】【F:frontend/src/pages/AdminPromptsPage.tsx†L97-L122】

- **테스트케이스 생성 (`testcase-generation`)**
  - 프론트엔드: `ProjectManagementPage`에서 메뉴 정의와 필수 문서 업로드 UX를 관리합니다.【F:frontend/src/pages/ProjectManagementPage.tsx†L156-L183】
  - 백엔드: 공통 생성 라우트가 템플릿(`_STANDARD_TEMPLATE_POPULATORS`)을 통해 결과 XLSX를 반환합니다.【F:backend/app/routes/drive.py†L241-L430】【F:backend/app/routes/drive.py†L73-L117】
  - 프롬프트 관리자: 테스트케이스용 지시문과 섹션은 `PromptConfigService`에 기본값으로 존재하며, 관리자 화면에서 편집됩니다.【F:backend/app/services/prompt_config.py†L195-L252】【F:frontend/src/pages/AdminPromptsPage.tsx†L97-L122】

- **결함 리포트 (`defect-report`)**
  - 프론트엔드: 메뉴 카드와 그리드 업로더, 결함 미리보기 토글 등을 `ProjectManagementPage`에서 정의합니다.【F:frontend/src/pages/ProjectManagementPage.tsx†L184-L197】【F:frontend/src/pages/ProjectManagementPage.tsx†L531-L620】
  - 백엔드: 결함 메모 정제, 표 재작성, 컴파일 등 전용 엔드포인트가 `drive.py`에 구현되어 있습니다.【F:backend/app/routes/drive.py†L200-L238】【F:backend/app/routes/drive.py†L432-L620】
  - 프롬프트 관리자: 결함 리포트 프롬프트와 첨부 활용 지침은 `PromptConfigService`에서 `defect-report` 키로 관리합니다.【F:backend/app/services/prompt_config.py†L253-L295】【F:frontend/src/pages/AdminPromptsPage.tsx†L97-L122】

- **보안성 리포트 (`security-report`)**
  - 프론트엔드: Invicti HTML만 허용하는 업로드 제한을 `ProjectManagementPage` 메뉴 정의에서 설정합니다.【F:frontend/src/pages/ProjectManagementPage.tsx†L198-L211】
  - 백엔드: 생성 라우트가 보안성 분기에서 Invicti 파일 검증과 CSV 응답 생성을 처리하며, 실제 변환 로직은 `SecurityReportService`가 담당합니다.【F:backend/app/routes/drive.py†L241-L301】【F:backend/app/services/security_report/service.py†L44-L148】
  - 프롬프트 관리자: 보안 리포트 템플릿과 작성 지침은 `PromptConfigService` 기본 설정으로 유지되고, 관리자 화면에서 수정 가능합니다.【F:backend/app/services/prompt_config.py†L296-L333】【F:frontend/src/pages/AdminPromptsPage.tsx†L97-L122】

- **성능 평가 리포트 (`performance-report`)**
  - 프론트엔드: 메뉴 카드와 허용 확장자는 `ProjectManagementPage`에서 정의되어 다른 메뉴와 동일한 업로드 UX를 사용합니다.【F:frontend/src/pages/ProjectManagementPage.tsx†L213-L220】
  - 백엔드: 전용 엔드포인트는 없으며 `/drive/projects/{project_id}/generate` 공통 흐름과 `AIGenerationService.generate_csv`를 공유합니다. 새로운 후처리가 필요하면 이 라우트를 기준으로 분기 로직을 추가하세요.【F:backend/app/routes/drive.py†L241-L430】
  - 프롬프트 관리자: 기본 프롬프트는 `performance-report` 키로 제공되며 관리자 페이지에서 유지보수합니다.【F:backend/app/services/prompt_config.py†L334-L347】【F:frontend/src/pages/AdminPromptsPage.tsx†L97-L122】

## 7. 참고 링크

- FastAPI 문서: https://fastapi.tiangolo.com/
- Google Drive API: https://developers.google.com/drive
- OpenAI Responses API: https://platform.openai.com/docs/guides/realtime

필요한 정보가 누락되었거나 갱신이 필요한 경우, 이 문서를 업데이트한 뒤 팀원들에게 공유해주세요.
