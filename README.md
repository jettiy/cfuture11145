# Futures Terminal

웹 기반 Futures Terminal (TradingView + Auth + Chat + News + Signal + Admin)

## 기술 스택

- **Frontend**: Next.js 14 (React) + TypeScript + Tailwind CSS
- **Backend**: FastAPI + SQLite/PostgreSQL
- **Realtime**: WebSocket (채팅)
- **Jobs**: APScheduler (뉴스 수집 및 번역/요약)
- **Auth**: JWT + RBAC (member/pro/admin)

## 프로젝트 구조

```
futures-terminal/
├── backend/          # FastAPI 백엔드
├── frontend/         # Next.js 프론트엔드
└── shared/           # 공통 타입 정의
```

## 빠른 시작

### 1. 환경 설정

```bash
# 환경변수: .env는 커밋하지 않음. 예시만 사용.
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
# .env / .env.local 편집 후 실제 값 설정 (SECRET_KEY, LLM_API_KEY 등)
```

자세한 실행/배포: **RUN.md**, **DEPLOYMENT.md** 참고.

### 2. 백엔드 실행

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

### 3. 프론트엔드 실행

```bash
cd frontend
npm install
npm run dev
```

### 4. 전체 빌드

```bash
# 웹앱 빌드
npm run build
```

## 주요 기능

- ✅ 사용자 인증 (회원가입/로그인, JWT)
- ✅ TradingView 차트 (NASDAQ, HSI, GOLD, OIL)
- ✅ 실시간 채팅 (Global + 종목별 채널)
- ✅ 뉴스 수집 및 한글화
- ✅ 시그널 계산기 (타임프레임별 분석)
- ✅ Admin Console (사용자 관리, 상담 관리)

## 환경변수

### Backend (.env)
```
DATABASE_URL=postgresql://user:password@localhost:5432/futures_terminal
SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24
TV_SYMBOL_NASDAQ=NASDAQ:NAS100
TV_SYMBOL_HSI=HKEX:HSI1!
TV_SYMBOL_GOLD=COMEX:GC1!
TV_SYMBOL_OIL=NYMEX:CL1!
LLM_API_KEY=your-deepseek-api-key
LLM_API_URL=https://api.deepseek.com/v1/chat/completions
LLM_MODEL=deepseek-chat
```

### Frontend (.env.local)
```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

## API 문서

백엔드 실행 후: http://localhost:8000/docs

## 배포

### 웹 배포

프론트엔드를 빌드하고 정적 파일을 호스팅하거나, Next.js를 프로덕션 모드로 실행합니다.

```bash
cd frontend
npm run build
npm start
```

또는 Vercel, Netlify 등의 플랫폼에 배포할 수 있습니다.
