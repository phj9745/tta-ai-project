echo "Doppler Secrets(환경변수) 다운로드"

# 1. 백엔드 시크릿 다운로드
doppler secrets download --project tta-ai-project --config dev --format env --no-file > ./backend/.env

# 2. 프론트엔드 시크릿 다운로드
doppler secrets download --project tta-ai-project --config dev --format env --no-file > ./frontend/.env

echo ".env 파일 갱신 완료!"

# 3. Docker Compose 실행 (기존 컨테이너 내리고 새로 빌드하여 실행)
echo "🐳 Docker 컨테이너 실행 중..."
docker compose up --build