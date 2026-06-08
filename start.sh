#!/bin/bash
set -e

echo "============================================"
echo "  LSS ERP 시스템 시작"
echo "============================================"

# 환경 설정 파일 확인
if [ ! -f "backend/.env" ]; then
    echo "[INFO] .env 파일 생성 중..."
    cp backend/.env.example backend/.env
    echo "[!] backend/.env 파일을 열어 DB 설정을 확인하세요."
fi

# Python 가상환경 확인
if [ ! -d "backend/venv" ]; then
    echo "[INFO] Python 가상환경 생성 중..."
    python3 -m venv backend/venv
fi

# 가상환경 활성화 및 패키지 설치
echo "[INFO] Python 패키지 설치 중..."
source backend/venv/bin/activate
pip install -r backend/requirements.txt -q

# Node.js 패키지 설치
if [ ! -d "frontend/node_modules" ]; then
    echo "[INFO] Node.js 패키지 설치 중..."
    cd frontend && npm install && cd ..
fi

# 프론트엔드 빌드
echo "[INFO] 프론트엔드 빌드 중..."
cd frontend && npm run build && cd ..

# 백엔드 서버 시작
echo ""
echo "============================================"
echo "  서버 시작: http://localhost:8000"
echo "  API 문서:  http://localhost:8000/api/docs"
echo "  초기 로그인: admin / admin"
echo "============================================"
echo ""

cd backend
export PYTHONPATH=$(pwd)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
