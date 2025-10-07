# tta-ai-project
AI-ON 업무혁신 공모전을 위해 제작된 **TTA AI 프로젝트 허브**의 프론트엔드 애플리케이션입니다. Google Drive와 연동해 프로젝트 자료를 관리하고, AI 생성 업무를 지원하며, 관리자 전용 프롬프트 편집 기능을 제공합니다.

## 화면 구성 개요

### 공통 상단(AppShell)
로그인 후 모든 화면에서는 상단 헤더에 세 가지 주요 버튼이 노출됩니다.【F:frontend/src/app/components/AppShell.tsx†L5-L45】

- **구글 드라이브**: `openGoogleDriveWorkspace` 함수를 호출해 프로젝트 전용 Google Drive 워크스페이스를 새 창으로 엽니다.【F:frontend/src/App.tsx†L24-L27】
- **프롬프트 관리자**: 관리자 전용 프롬프트 편집 페이지(`/admin/prompts`)로 이동합니다.【F:frontend/src/App.tsx†L29-L32】
- **로그아웃**: 저장된 인증 정보를 삭제하고 로그인 화면으로 이동합니다.【F:frontend/src/App.tsx†L20-L23】

### 로그인 페이지
로그인이 되지 않은 상태에서는 항상 로그인 페이지가 렌더링됩니다.【F:frontend/src/app/routing/resolvePage.tsx†L17-L32】 `GoogleLoginCard` 컴포넌트가 Google OAuth 연동을 담당하며 다음과 같은 기능을 제공합니다.【F:frontend/src/pages/LoginPage.tsx†L1-L16】【F:frontend/src/components/GoogleLoginCard.tsx†L1-L119】

- **Google 계정으로 로그인** 버튼: 백엔드의 `/auth/google/login` 엔드포인트로 리디렉션해 인증을 시작합니다.【F:frontend/src/components/GoogleLoginCard.tsx†L76-L98】
- 인증 성공 시 성공 메시지를 표시하고 `/projects` 페이지로 자동 이동합니다.【F:frontend/src/components/GoogleLoginCard.tsx†L33-L74】
- 인증 실패 시 실패 메시지를 보여주고 저장된 인증 정보를 초기화합니다.【F:frontend/src/components/GoogleLoginCard.tsx†L68-L74】

### Drive 프로젝트 페이지
로그인 후 `/projects` 혹은 `/drive` 경로에서는 Drive 프로젝트 설정 화면이 나타납니다.【F:frontend/src/app/routing/resolvePage.tsx†L20-L24】 주요 구성 요소와 버튼은 다음과 같습니다.【F:frontend/src/pages/DriveSetupPage.tsx†L1-L165】

- **Drive 상태 확인**: 페이지 진입 시 백엔드의 `/drive/gs/setup`을 호출해 프로젝트 루트 폴더를 생성하거나 조회합니다.【F:frontend/src/pages/DriveSetupPage.tsx†L34-L83】
- **다시 시도** 버튼: 오류 발생 시 호출을 재시도합니다.【F:frontend/src/pages/DriveSetupPage.tsx†L85-L107】
- **프로젝트 선택 리스트**: 기존 프로젝트 폴더를 클릭하면 해당 프로젝트 관리 페이지로 이동합니다.【F:frontend/src/components/drive/DriveProjectsList.tsx†L9-L39】
- **새 프로젝트 만들기** 버튼: `ProjectCreationModal`을 열어 새로운 프로젝트 폴더와 기본 자료를 생성합니다.【F:frontend/src/pages/DriveSetupPage.tsx†L109-L153】
- **ProjectCreationModal** 내 **생성** 버튼: 선택한 파일을 업로드해 `/drive/projects` 엔드포인트로 프로젝트 생성을 요청합니다. 업로드 전 필수 파일 검증, 업로드 중 로딩 오버레이, 실패 시 오류 메시지를 제공합니다.【F:frontend/src/components/ProjectCreationModal.tsx†L1-L142】
- **취소** 버튼: 모달을 닫고 입력 상태를 초기화합니다.【F:frontend/src/components/ProjectCreationModal.tsx†L118-L135】

### 프로젝트 관리 페이지
프로젝트를 선택하면 `/projects/:projectId` 경로에서 프로젝트 관리 화면이 렌더링됩니다.【F:frontend/src/app/routing/resolvePage.tsx†L26-L30】 좌측 메뉴에서 다섯 가지 생성 업무(기능 리스트, 테스트케이스, 결함 리포트, 보안성 리포트, 성능 평가 리포트)를 전환하며 각 업무별 업로드 요건과 버튼이 다르게 동작합니다.【F:frontend/src/pages/ProjectManagementPage.tsx†L1-L220】

- **좌측 메뉴 버튼**: 메뉴를 클릭하면 해당 업무의 지시문, 업로드 형식, 필수 문서 조건이 갱신됩니다.【F:frontend/src/pages/ProjectManagementPage.tsx†L209-L242】
- **다른 프로젝트 선택** 버튼: `/projects` 페이지로 이동해 다른 프로젝트를 고를 수 있습니다.【F:frontend/src/pages/ProjectManagementPage.tsx†L243-L258】【F:frontend/src/pages/ProjectManagementPage.tsx†L659-L693】
- **파일 업로더(FileUploader)**: 업무에 따라 단일/다중 업로드, 허용 확장자, 격자형 표시 등을 제어합니다. 필수 문서가 있는 경우에는 문서별 업로드 영역과 추가 파일 리스트를 제공합니다.【F:frontend/src/pages/ProjectManagementPage.tsx†L259-L460】【F:frontend/src/pages/ProjectManagementPage.tsx†L694-L790】
- **추가 파일 문서 종류 입력 필드**: 추가 업로드한 파일마다 문서 설명을 입력해야 하며, 미입력 시 생성이 막힙니다.【F:frontend/src/pages/ProjectManagementPage.tsx†L322-L382】【F:frontend/src/pages/ProjectManagementPage.tsx†L742-L775】
- **생성하기** 버튼: 선택한 메뉴 ID와 파일들을 `/drive/projects/:id/generate` 엔드포인트에 전달하여 결과 생성 작업을 요청합니다. 요청 중에는 AbortController를 활용해 중복 요청을 취소하고 로딩 상태를 표시합니다.【F:frontend/src/pages/ProjectManagementPage.tsx†L466-L610】【F:frontend/src/pages/ProjectManagementPage.tsx†L800-L820】
- **CSV 다운로드** 버튼: 성공적으로 생성된 결과가 있을 때만 표시되며, Blob URL로 제공된 CSV 파일을 다운로드합니다.【F:frontend/src/pages/ProjectManagementPage.tsx†L611-L658】【F:frontend/src/pages/ProjectManagementPage.tsx†L821-L840】
- **다시 생성하기** 버튼: 현재 메뉴의 상태를 초기화하고 새로운 파일 업로드 및 생성 요청이 가능하도록 합니다.【F:frontend/src/pages/ProjectManagementPage.tsx†L621-L658】【F:frontend/src/pages/ProjectManagementPage.tsx†L829-L836】
- **상태 메시지 영역**: 로딩·오류·성공 상태에 따라 안내 문구를 표시합니다.【F:frontend/src/pages/ProjectManagementPage.tsx†L612-L658】【F:frontend/src/pages/ProjectManagementPage.tsx†L810-L838】

### 관리자 페이지(프롬프트 관리자)
상단의 **프롬프트 관리자** 버튼을 클릭하면 관리자 전용 페이지가 열립니다.【F:frontend/src/App.tsx†L29-L32】 프롬프트 설정, 미리보기, 로그 확인 등 여러 관리 기능을 지원하며 버튼 동작이 세분화되어 있습니다.【F:frontend/src/pages/AdminPromptsPage.tsx†L1-L515】【F:frontend/src/pages/AdminPromptsPage.tsx†L516-L1038】

- **프로젝트 페이지로 돌아가기**: 프로젝트 목록 화면으로 이동합니다.【F:frontend/src/pages/AdminPromptsPage.tsx†L558-L569】
- **기본값 적용**: 서버에서 제공하는 기본 프롬프트 설정으로 현재 카테고리 구성을 초기화합니다.【F:frontend/src/pages/AdminPromptsPage.tsx†L370-L399】【F:frontend/src/pages/AdminPromptsPage.tsx†L536-L583】
- **되돌리기**: 페이지 진입 이후 저장하지 않고 수정한 내용을 서버에서 내려받은 원본 상태로 되돌립니다.【F:frontend/src/pages/AdminPromptsPage.tsx†L341-L368】【F:frontend/src/pages/AdminPromptsPage.tsx†L558-L569】
- **저장**: 수정된 프롬프트 구성을 백엔드 `/admin/prompts` 엔드포인트에 `PUT`으로 저장합니다. 저장 중 버튼이 비활성화되며 결과 메시지가 상태 영역에 표시됩니다.【F:frontend/src/pages/AdminPromptsPage.tsx†L301-L339】【F:frontend/src/pages/AdminPromptsPage.tsx†L558-L577】
- **프롬프트 카테고리 목록**: 좌측 내비게이션에서 업무 유형별 프롬프트(기능리스트, 테스트케이스 등)를 선택할 수 있습니다.【F:frontend/src/pages/AdminPromptsPage.tsx†L520-L557】
- **시스템/사용자 프롬프트 입력 필드**: 텍스트 영역에 입력한 내용이 즉시 상태에 반영되며 미리보기에도 적용됩니다.【F:frontend/src/pages/AdminPromptsPage.tsx†L572-L626】
- **+ 지침 추가**: 추가 사용자 지침 블록을 생성합니다. 블록마다 제목, 내용, 활성화 여부를 설정하고 **삭제** 버튼으로 제거할 수 있습니다.【F:frontend/src/pages/AdminPromptsPage.tsx†L156-L210】【F:frontend/src/pages/AdminPromptsPage.tsx†L626-L699】
- **첨부 안내 문구 필드**: 첨부 섹션 제목, 소개 문구, 마무리 문장, 형식 경고를 세밀하게 편집합니다.【F:frontend/src/pages/AdminPromptsPage.tsx†L103-L143】【F:frontend/src/pages/AdminPromptsPage.tsx†L701-L741】
- **첨부 설명 템플릿 입력**: 첨부 파일 목록을 렌더링할 때 사용할 문자열 템플릿을 편집합니다.【F:frontend/src/pages/AdminPromptsPage.tsx†L42-L59】【F:frontend/src/pages/AdminPromptsPage.tsx†L743-L752】
- **+ 컨텍스트 추가**: 내장 컨텍스트(사전 제공 문서)를 추가하고 이름, 설명, 파일 경로, 렌더링 방식, 프롬프트 포함 여부, 첨부 목록 노출 여부를 설정합니다.【F:frontend/src/pages/AdminPromptsPage.tsx†L59-L102】【F:frontend/src/pages/AdminPromptsPage.tsx†L754-L842】
- **모델 파라미터 입력**: Temperature, Top P, Max Output Tokens, Presence/Frequency Penalty를 수정합니다.【F:frontend/src/pages/AdminPromptsPage.tsx†L843-L899】
- **실시간 미리보기**: 현재 설정으로 생성될 사용자 프롬프트를 즉시 확인하고, **전체 화면** 버튼을 눌러 모달에서 크게 볼 수 있습니다.【F:frontend/src/pages/AdminPromptsPage.tsx†L112-L154】【F:frontend/src/pages/AdminPromptsPage.tsx†L901-L940】
- **최근 요청 기록**: `/admin/prompts/logs` API에서 최근 50건을 조회하여 메뉴, 프로젝트 ID, 프롬프트 전문 등을 확인합니다. **새로고침** 버튼으로 재요청하며, 각 항목의 `details` 요소를 펼쳐 전문을 열람할 수 있습니다.【F:frontend/src/pages/AdminPromptsPage.tsx†L216-L300】【F:frontend/src/pages/AdminPromptsPage.tsx†L942-L1007】
- **프롬프트 미리보기 모달**: 전체 화면 보기 버튼을 누르면 모달이 열리고 **닫기** 버튼으로 종료합니다.【F:frontend/src/pages/AdminPromptsPage.tsx†L1009-L1038】

## 첨부 설명 템플릿 키 안내
관리자 페이지의 첨부 설명 템플릿에서는 다음 플레이스홀더를 사용할 수 있습니다.【F:frontend/src/pages/AdminPromptsPage.tsx†L42-L59】

- `{{index}}`: 첨부 순번 (1부터 시작)
- `{{descriptor}}`: 파일 이름과 확장자를 조합한 기본 설명
- `{{label}}`: 사용자가 입력한 친숙한 이름 (없으면 파일 이름)
- `{{description}}`: 파일 설명
- `{{extension}}`: 파일 확장자 (예: pdf, pptx)
- `{{doc_id}}`: 필수 문서 식별자 (해당 없으면 빈 문자열)
- `{{notes}}`: 추가 비고
- `{{source_path}}`: 원본 경로
- `{{context_summary}}`: 여러 첨부 파일의 레이블을 쉼표로 연결한 요약 (미리보기에서 확인 가능)【F:frontend/src/pages/AdminPromptsPage.tsx†L118-L154】

이 템플릿을 활용하면 첨부 파일 목록을 일관된 형식으로 구성하여 모델에 전달할 수 있습니다.
