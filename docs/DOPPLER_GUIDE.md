# Doppler 사용 가이드 (Doppler Usage Guide)

우리 프로젝트는 환경 변수의 파편화와 보안 문제를 해결하기 위해 **Doppler**를 통합했습니다. 이제 더 이상 `.env` 파일을 수동으로 주고받을 필요가 없습니다.

## 1. 초기 세팅 (개발자 한 번만 수행)

### (A) Doppler CLI 설치
*   **Windows (PowerShell)**:
    winget install doppler.doppler

*   **macOS**: `brew install dopplerhq/cli/doppler`

*   **Linux (Ubuntu/WSL)**:
    sudo apt-get update && sudo apt-get install -y apt-transport-https ca-certificates curl gnupg
    curl -sLf --retry 3 --tlsv1.2 --proto "=https" 'https://packages.doppler.com/public/cli/gpg.DE2A7741A397C129.key' | sudo gpg --dearmor -o /usr/share/keyrings/doppler-archive-keyring.gpg

    echo "deb [signed-by=/usr/share/keyrings/doppler-archive-keyring.gpg] https://packages.doppler.com/public/cli/deb/debian any-version main" | sudo tee /etc/apt/sources.list.d/doppler-cli.list

    sudo apt-get update && sudo apt-get install doppler

### (B) 로그인 및 프로젝트 연결
터미널에서 프로젝트 루트 디렉토리로 이동한 후 실행하세요:
```bash
# 1. 브라우저가 열리면 가입/로그인 진행
doppler login

# 2. 프로젝트 연결 (doppler.yaml 설정에 따라 자동으로 연결됨)
doppler setup
```

## 2. 개발 시 사용법

### (A) 로컬 실행 (Hot Selection)
기존의 `npm run dev` 대신 앞에 `doppler run --`를 붙여서 실행합니다. 이렇게 하면 `.env` 파일 없이도 실시간으로 Doppler의 값을 주입합니다.

*   **백엔드**: `doppler run -- python main.py`
*   **프론트엔드**: `doppler run -- npm run dev`

### (B) .env 파일이 꼭 필요한 경우 (Legacy/Docker용)
만약 `.env` 파일 형태로 물리적으로 추출해야 한다면 아래 명령어를 쓰세요 (단, Git에 올리지 않도록 주의!):
```bash
doppler secrets download --project tta-ai-project --config dev --format env > .env
```

## 3. 새로운 환경 변수 추가
1. [Doppler Dashboard](https://dashboard.doppler.com/)에 접속합니다.
2. `tta-ai-project` 프로젝트의 `dev` 설정을 선택합니다.
3. 새로운 KEY=VALUE를 추가하고 저장(Save)합니다.
4. 팀원들은 별도 작업 없이 다음 `doppler run` 실행 시 자동으로 최신 값을 사용하게 됩니다.

## 4. 서버(Production) 환경 적용 - 가장 쉬운 방법 (방식 A)

서버에서는 보안을 위해 `doppler login` 대신 **Service Token**을 사용합니다.

### (A) 서비스 토큰 발급
1. [Doppler 대시보드](https://dashboard.doppler.com/) -> 프로젝트 선택 -> `dev` 설정 클릭.
2. 좌측 메뉴의 **[Access]** 클릭 -> **[Service Tokens]** -> **[Generate]** 클릭.
3. 생성된 토큰(`dp.pt.xxxx...`)을 복사해둡니다.

### (B) 서버 환경 변수 설정 (최초 1회)
서버의 WSL 터미널(또는 OS)에 토큰을 등록합니다.
```bash
# .bashrc 등에 추가하여 자동 로드되게 하거나, 현재 세션에 설정
export DOPPLER_TOKEN="방금_복사한_토큰_값"
```

### (C) 한 줄 배포 명령어
이제 서버에서 배포할 때는 아래 명령어만 치면 됩니다. (파일 수정 필요 없음!)
```bash
# 1. Doppler에서 최신 키를 가져와서 .env 생성
doppler secrets download --project tta-ai-project --config dev --format env --no-file > ./backend/.env
doppler secrets download --project tta-ai-project --config dev --format env --no-file > ./frontend/.env

# 2. 도커 컴포즈 실행
docker compose up --build
```
> [!TIP]
> 이제 대시보드에서 키를 바꾸고 서버에서 위 명령어만 다시 치면, 즉시 최신 키가 반영된 서버가 뜹니다!
