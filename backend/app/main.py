import os
from fastapi import FastAPI
from dotenv import load_dotenv

# .env 파일에서 환경 변수(API Key) 불러오기
load_dotenv()

# FastAPI 인스턴스 생성
app = FastAPI()

# 루트 엔드포인트 ('/')
@app.get("/")
def read_root():
    # OpenAI API Key 로딩 되었는지 확인
    api_key = os.getenv("OPENAI_API_KEY")
    return {
        "Project": "TTA-AI-Project",
        "Status": "Running",
        "OpenAI API Key": f"{api_key[:5]}..." if api_key else "API 키 못찾았지롱"
    }