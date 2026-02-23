# Doppler 사용 가이드

> 우리 프로젝트는 환경 변수의 파편화와 보안 문제를 해결하기 위해 **Doppler**를 통합했습니다. `.env` 파일을 수동으로 주고받을 필요가 없습니다.

---

## 1. 초기 세팅 (개발자 한 번만 수행)

### (A) Doppler CLI 설치

* **Windows (PowerShell)**:
  ```powershell
  winget install doppler.doppler
  ```

* **macOS**:
  ```bash
  brew install dopplerhq/cli/doppler
  ```

* **Linux (Ubuntu/WSL)**:
  ```bash
  sudo apt-get update && sudo apt-get install -y apt-transport-https ca-certificates curl gnupg
  curl -sLf --retry 3 --tlsv1.2 --proto "=https" \
    'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' \
    | sudo gpg --dearmor -o /usr/share/keyrings/doppler-archive-keyring.gpg
  echo "deb [signed-by=/usr/share/keyrings/doppler-archive-keyring.gpg] \
    https://packages.doppler.com/public/cli/deb/debian any-version main" \
    | sudo tee /etc/apt/sources.list.d/doppler-cli.list
  sudo apt-get update && sudo apt-get install doppler
  ```

### (B) 로그인 및 프로젝트 연결

터미널에서 프로젝트 루트 디렉토리로 이동한 후 실행하세요:

```bash
# 1. 브라우저가 열리면 가입/로그인 진행
doppler login

# 2. 프로젝트 연결 (doppler.yaml 설정에 따라 자동으로 연결됨)
doppler setup
```

---

## 2. 개발 시 사용법

### (A) 로컬 실행 (Doppler 주입)

기존의 실행 명령 앞에 `doppler run --`를 붙이면 `.env` 파일 없이도 실시간으로 Doppler의 값을 주입합니다.

* **백엔드**: `doppler run -- uvicorn app.main:app --reload`
* **프론트엔드**: `doppler run -- npm run dev`

### (B) .env 파일이 꼭 필요한 경우 (Legacy/Docker용)

만약 `.env` 파일 형태로 물리적으로 추출해야 한다면 아래 명령어를 쓰세요 (Git에 올리지 않도록 주의!):

```bash
doppler secrets download --project tta-ai-project --config dev --format env > .env
```

---

## 3. 새로운 환경 변수 추가

1. [Doppler Dashboard](https://dashboard.doppler.com/)에 접속합니다.
2. `tta-ai-project` 프로젝트의 `dev` 설정을 선택합니다.
3. 새로운 KEY=VALUE를 추가하고 저장(Save)합니다.
4. 팀원들은 별도 작업 없이 다음 `doppler run` 실행 시 자동으로 최신 값을 사용하게 됩니다.

---

## 4. 서버(Production) 환경 적용

서버에서는 보안을 위해 `doppler login` 대신 **Service Token**을 사용합니다.

### (A) 서비스 토큰 발급

1. [Doppler 대시보드](https://dashboard.doppler.com/) → 프로젝트 선택 → `dev` 설정 클릭
2. 좌측 메뉴의 **[Access]** 클릭 → **[Service Tokens]** → **[Generate]** 클릭
3. 생성된 토큰(`dp.pt.xxxx...`)을 복사해둡니다.

### (B) 서버 환경 변수 설정 (최초 1회)

서버의 WSL 터미널(또는 OS)에 토큰을 등록합니다.

```bash
# .bashrc 또는 .profile 등에 추가하여 자동 로드되게 합니다
export DOPPLER_TOKEN="방금_복사한_토큰_값"
```

### (C) 원클릭 배포 (server_start.sh)

프로젝트 루트에 포함된 `server_start.sh`를 실행하면 **시크릿 다운로드 → Docker 배포**가 한 번에 이루어집니다:

```bash
bash server_start.sh
```

이 스크립트는 내부적으로 다음 작업을 수행합니다:

1. Doppler에서 최신 시크릿을 가져와 `backend/.env`에 저장
2. `VITE_` 접두사 변수만 필터링하여 `frontend/.env`에 저장
3. `docker compose up --build`로 전체 서비스 실행

> [!TIP]
> 대시보드에서 키를 변경한 뒤 서버에서 `bash server_start.sh`만 다시 실행하면 즉시 최신 키가 반영됩니다!

---

## 5. 참고

- 프로젝트 설정 파일: `doppler.yaml` (루트 디렉터리)
- Doppler 공식 문서: https://docs.doppler.com/
- 환경 변수 목록 및 설명: [협업 가이드 §3](COLLABORATION_GUIDE.md#3-환경-변수-및-비밀-관리) 참고
