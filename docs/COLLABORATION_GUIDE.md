# 🤝 TestMate 협업 가이드

> 새 팀원이 빠르게 전체 구조와 핵심 개념을 파악할 수 있도록 정리한 온보딩 문서입니다. 기존 `README.md`와 별도로 유지합니다.

## 1. 시스템 구성 요약

- **Frontend**: React 19 + TypeScript 5.8 + Vite 7 기반 단일 페이지 애플리케이션. `App.tsx`에서 인증 상태와 경로에 따라 페이지를 렌더링하며 상단 `AppShell`을 통해 드라이브/프롬프트/로그아웃 액션을 제공합니다.
- **Backend**: FastAPI 0.117. `create_app()`에서 CORS 설정 및 라우터를 묶고, 의존성 컨테이너를 `app.state.container`에 보관합니다.
- **데이터/외부 연동**: Google OAuth & Drive, Anthropic API. 환경변수는 `Settings` 데이터클래스로 로드하며 토큰/프롬프트 파일 경로도 여기서 설정합니다.
- **시크릿 관리**: Doppler를 사용하여 환경 변수를 중앙 관리합니다. 자세한 내용은 [Doppler 사용 가이드](DOPPLER_GUIDE.md)를 참고하세요.

## 2. 주요 디렉터리 맵

```
root
├── backend/              # FastAPI 서비스
│   ├── app/              # 애플리케이션 코드
│   │   ├── routes/       # REST 엔드포인트 정의 (auth, drive, prompts)
│   │   ├── services/     # Drive, OAuth, 프롬프트, AI 호출, 보안/성능 리포트 로직
│   │   ├── config.py     # Settings 데이터클래스 (환경 변수 로드)
│   │   ├── container.py  # 서비스 인스턴스 생성/DI
│   │   └── token_store.py # Google OAuth 토큰 영속 저장소
│   ├── template/         # 표준 Excel/문서 템플릿
│   └── tests/            # FastAPI 유닛/통합 테스트
├── frontend/             # React 앱
│   ├── src/              # TSX/TS 소스
│   │   ├── app/          # 공용 레이아웃, 훅, 라우팅 로직
│   │   ├── components/   # 도메인별 UI 컴포넌트
│   │   └── pages/        # 실제 페이지 엔트리
│   └── package.json      # 의존성 및 스크립트
├── nginx/                # Nginx 리버스 프록시 설정
│   └── nginx.conf        # HTTPS 프록시 규칙
├── dev-certs/            # 자체 서명 SSL 인증서 (개발/서버용)
├── docker-compose.yml    # 백엔드 + 프론트엔드 + Nginx 동시 실행
├── doppler.yaml          # Doppler 프로젝트/환경 매핑
└── server_start.sh       # 원클릭 배포 스크립트 (Doppler → .env → Docker)
```

## 3. 환경 변수 및 비밀 관리

| 변수 | 설명 | 위치 |
| --- | --- | --- |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | Google OAuth 인증 정보 | `backend/app/config.py` |
| `FRONTEND_REDIRECT_URL` | 로그인 이후 리다이렉트 경로(CORS 기준) | `backend/app/config.py` |
| `GOOGLE_TOKEN_DB_PATH` | 발급 토큰 SQLite 경로 | `backend/app/config.py` |
| `ANTHROPIC_API_KEY`, `AI_MODEL` | Anthropic API 설정 (기본 모델: `claude-haiku-4-5-20251001`) | `backend/app/config.py` |
| `BUILTIN_TEMPLATE_ROOT` | 내장 프롬프트/템플릿 커스텀 루트 (선택) | `backend/app/config.py` |
| `VITE_API_BASE_URL` | 프론트엔드에서 사용하는 백엔드 API 엔드포인트 | `frontend/.env` |

- **Doppler를 통한 관리를 권장합니다.** 대시보드에서 변수 추가/수정 후 `doppler run` 또는 `server_start.sh`로 즉시 반영됩니다.
- 기본값은 `.env` 없이도 동작하도록 정의되어 있지만, 실제 환경에서는 `backend/.env` 파일(또는 Doppler)에 위 항목을 채워야 합니다.
- Google OAuth 토큰은 `TokenStorage`가 `google_tokens.db` (SQLite)에 저장하므로, `.gitignore`에 포함되어 있는지 확인합니다.

## 4. 로컬 개발 워크플로우

### 4.1 Docker Compose (권장)
1. `docker compose up --build`
2. 프론트엔드: http://localhost:5173
3. 백엔드: http://localhost:8000/docs (자동 리로드)
4. Nginx 프록시: https://localhost (자체 서명 SSL)
5. `.env`는 `backend/.env`와 `frontend/.env`를 작성하거나 Doppler를 사용

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

### 4.3 서버 배포 (server_start.sh)
Doppler 토큰이 설정된 서버에서 아래 한 줄로 배포할 수 있습니다:
```bash
bash server_start.sh
```
이 스크립트는 Doppler에서 시크릿을 `.env` 파일로 추출한 뒤 `docker compose up --build`를 실행합니다.

## 5. 서비스 컨테이너(Container) 구조

`backend/app/container.py`에서 모든 서비스 인스턴스를 생성하며, `app.state.container`를 통해 라우터에서 접근합니다.

| 서비스 | 클래스 | 역할 |
| --- | --- | --- |
| `oauth_service` | `GoogleOAuthService` | Google OAuth 인증 흐름 |
| `drive_service` | `GoogleDriveService` | Drive 폴더/파일 CRUD |
| `ai_generation_service` | `AIGenerationService` | Anthropic API 호출, 프롬프트 구성, 로그 기록 |
| `prompt_config_service` | `PromptConfigService` | 프롬프트 설정 직렬화 (`prompt_configs.json`) |
| `prompt_request_log_service` | `PromptRequestLogService` | 최근 요청 로그 (`prompt_requests.log`) |
| `security_report_service` | `SecurityReportService` | Invicti HTML 기반 보안 분석 리포트 |
| `performance_report_service` | `PerformanceReportService` | 성능 평가 리포트 생성 |
| `configuration_image_service` | `ConfigurationImageService` | 구성 이미지 분석·문서 생성 |

## 6. 핵심 도메인 로직 이해 포인트

### 6.1 Drive & 프로젝트 관리
- `/drive/gs/setup`, `/drive/projects` 등 주요 엔드포인트는 `backend/app/routes/drive.py`에 정의되어 있습니다.
- `_REQUIRED_MENU_DOCUMENTS` 매핑으로 메뉴별 필수 첨부 문서를 제한하며, 업로드 파일 확장자 검증도 수행합니다.
- 엑셀 출력은 `services/excel_templates` 하위 모듈에서 처리하며, 표준 양식(`template/`)을 로드해 채워 넣습니다.

### 6.2 프롬프트 관리 & AI 호출
- `AIGenerationService`는 Anthropic API 호출과 프롬프트 구성/로그 기록을 담당합니다.
- 관리자 화면에서 저장한 프롬프트 설정은 `PromptConfigService`가 `prompt_configs.json`으로 직렬화합니다.
- 최근 요청 로그는 `PromptRequestLogService`가 `prompt_requests.log` 파일에 Append 합니다.

### 6.3 보안/성능/구성 이미지 리포트
- `SecurityReportService`: Invicti HTML 보안 스캔 결과를 파싱하여 보안성 리포트를 생성합니다.
- `PerformanceReportService`: 성능 측정 데이터를 수집·분석하여 평가 리포트를 생성합니다.
- `ConfigurationImageService`: 업로드된 구성도 이미지를 분석하여 관련 문서를 자동 생성합니다.

### 6.4 프론트엔드 라우팅 & 상태 관리
- `useAuthStatus`, `useRouteGuards`, `resolvePage` 조합으로 로그인 여부에 따른 페이지 가드를 구현합니다.
- 상단 `AppShell`은 공통 네비게이션과 핸들러(`openGoogleDriveWorkspace`, `clearAuthentication`, 관리자 이동)를 props로 받아 동작합니다.
- Google OAuth 토큰/프로젝트 정보는 `localStorage` 기반 유틸(`frontend/src/auth.ts`, `frontend/src/drive.ts`)을 통해 관리합니다.

## 7. 주요 페이지 구성

| 페이지 | 파일 | 설명 |
| --- | --- | --- |
| 로그인 | `LoginPage.tsx` | Google OAuth 로그인 |
| Drive 프로젝트 | `DriveSetupPage.tsx` | 프로젝트 생성·선택·관리 |
| 프로젝트 관리 | `ProjectManagementPage.tsx` | 문서 업로드 및 AI 생성 허브 |
| 기능 리스트 편집 | `FeatureListEditPage.tsx` | 생성된 기능 리스트 수정·추가·삭제 |
| 테스트케이스 편집 | `TestcaseEditPage.tsx` | 생성된 테스트케이스 수정·추가·삭제 |
| 결함 리포트 편집 | `DefectReportEditPage.tsx` | 결함 리포트 행 편집 및 최종 반영 |
| 구성 이미지 편집 | `ConfigurationImageEditPage.tsx` | 구성 이미지 분석 결과 수정 |
| 프롬프트 관리 | `AdminPromptsPage.tsx` | 관리자 전용 프롬프트 설정 |

## 8. 생성 메뉴별 파일 가이드

각 생성 메뉴는 프론트엔드 업로드 UI, 백엔드 생성/스프레드시트 반영 라우터, 그리고 관리자 프롬프트 설정으로 구성되어 있습니다. 변경 시 아래 파일을 함께 확인하세요.

- **기능리스트 생성 (`feature-list`)**
  - 프론트엔드: `ProjectManagementPage`에서 메뉴 정의·필수 문서 구성, `FeatureListEditPage`에서 결과 편집
  - 백엔드: `/drive/projects/{project_id}/generate` 라우트가 필수 문서 검증과 스프레드시트 업데이트 처리
  - 프롬프트 관리자: `PromptConfigService`의 `feature-list` 엔트리로 정의

- **테스트케이스 생성 (`testcase-generation`)**
  - 프론트엔드: `ProjectManagementPage`에서 메뉴 정의, `TestcaseEditPage`에서 결과 편집
  - 백엔드: 공통 생성 라우트가 템플릿(`_STANDARD_TEMPLATE_POPULATORS`)을 통해 결과 XLSX 반환
  - 프롬프트 관리자: `PromptConfigService`에 기본값으로 존재

- **결함 리포트 (`defect-report`)**
  - 프론트엔드: `ProjectManagementPage`에서 메뉴 카드·그리드 업로더, `DefectReportEditPage`에서 편집
  - 백엔드: 결함 메모 정제, 표 재작성, 컴파일 등 전용 엔드포인트가 `drive.py`에 구현
  - 프롬프트 관리자: `PromptConfigService`에서 `defect-report` 키로 관리

- **보안성 리포트 (`security-report`)**
  - 프론트엔드: `ProjectManagementPage`에서 Invicti HTML만 허용하는 업로드 제한
  - 백엔드: `SecurityReportService`가 Invicti 파일 검증과 보안 분석 담당
  - 프롬프트 관리자: `PromptConfigService` 기본 설정으로 유지

- **성능 평가 리포트 (`performance-report`)**
  - 프론트엔드: `ProjectManagementPage`에서 메뉴 카드·허용 확장자 관리
  - 백엔드: `PerformanceReportService`가 성능 데이터 분석 담당
  - 프롬프트 관리자: `PromptConfigService`의 `performance-report` 키로 관리

- **구성 이미지 (`configuration-image`)**
  - 프론트엔드: `ProjectManagementPage`에서 이미지 업로드 UI, `ConfigurationImageEditPage`에서 결과 편집
  - 백엔드: `ConfigurationImageService`가 이미지 분석·문서 생성 담당

## 9. 참고 링크

- FastAPI 문서: https://fastapi.tiangolo.com/
- Google Drive API: https://developers.google.com/drive
- Anthropic API: https://docs.anthropic.com/claude/reference/messages_post
- Doppler 문서: https://docs.doppler.com/

필요한 정보가 누락되었거나 갱신이 필요한 경우, 이 문서를 업데이트한 뒤 팀원들에게 공유해주세요.
