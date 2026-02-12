# Doppler 사용 가이드 (Doppler Usage Guide)

우리 프로젝트는 환경 변수의 파편화와 보안 문제를 해결하기 위해 **Doppler**를 통합했습니다. 이제 더 이상 `.env` 파일을 수동으로 주고받을 필요가 없습니다.

## 1. 초기 세팅 (개발자 한 번만 수행)

### (A) Doppler CLI 설치
*   **Windows (PowerShell)**:
    ```powershell
    iwr -useb ""https://docs.doppler.com/install.ps1"" | iex
    ```
*   **macOS**: `brew install dopplerhq/cli/doppler`
*   **Linux (Ubuntu/WSL)**:
    ```bash
    (curl -Ls https://cli.doppler.com/install.sh || wget -qO- https://cli.doppler.com/install.sh) | sudo sh
    ```

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
doppler secrets download --no-confirm --format env > .env
```

## 3. 새로운 환경 변수 추가
1. [Doppler Dashboard](https://dashboard.doppler.com/)에 접속합니다.
2. `tta-ai-project` 프로젝트의 `dev` 설정을 선택합니다.
3. 새로운 KEY=VALUE를 추가하고 저장(Save)합니다.
4. 팀원들은 별도 작업 없이 다음 `doppler run` 실행 시 자동으로 최신 값을 사용하게 됩니다.

## 4. 서버(생산) 환경 적용
서버에서는 **서비스 토큰(Service Token)**을 발급받아 `DOPPLER_TOKEN` 환경변수만 설정해주면 안전하게 값을 가져올 수 있습니다.
