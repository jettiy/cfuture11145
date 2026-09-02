# 배포 가이드

## 로컬 개발 환경 설정

### 1. 데이터베이스 설정

```bash
# PostgreSQL 설치 후
createdb futures_terminal

# 또는 psql에서
CREATE DATABASE futures_terminal;
```

### 2. 백엔드 설정

```bash
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt

# .env 파일 생성
cp .env.example .env
# .env 파일 편집하여 데이터베이스 URL 등 설정

# 데이터베이스 초기화
python -m app.init_db

# 서버 실행
uvicorn main:app --reload
```

### 3. 프론트엔드 설정

```bash
cd frontend
npm install

# .env.local 파일 생성
cp .env.example .env.local

# 개발 서버 실행
npm run dev
```

### 4. Electron 개발 모드

```bash
# 프론트엔드 개발 서버가 실행 중이어야 함
cd electron
npm install
npm run dev
```

## 프로덕션 빌드

### 웹앱 빌드

```bash
# 프론트엔드 빌드
cd frontend
npm run build

# 백엔드는 별도 서버에서 실행
cd backend
uvicorn main:app --host 0.0.0.0 --port 8000
```

### Electron EXE 빌드

```bash
# 1. 프론트엔드 빌드 (필수)
cd frontend
npm run build

# 2. Electron 빌드
cd electron
npm run build:win
```

빌드된 EXE는 `electron/dist/` 디렉토리에 생성됩니다.

## 환경변수 예시

### Backend (.env)

```env
DATABASE_URL=postgresql://user:password@localhost:5432/futures_terminal
SECRET_KEY=your-secret-key-change-in-production-min-32-chars
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=24

TV_SYMBOL_NASDAQ=NASDAQ:NAS100
TV_SYMBOL_HSI=HKEX:HSI1!
TV_SYMBOL_GOLD=COMEX:GC1!
TV_SYMBOL_OIL=NYMEX:CL1!

LLM_API_KEY=sk-...
LLM_API_URL=https://api.openai.com/v1
LLM_MODEL=gpt-3.5-turbo

NEWS_RSS_FEEDS=https://feeds.finance.yahoo.com/rss/2.0/headline
NEWS_UPDATE_INTERVAL_MINUTES=30
```

### Frontend (.env.local)

```env
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
NEXT_PUBLIC_TV_SYMBOL_NASDAQ=NASDAQ:NAS100
NEXT_PUBLIC_TV_SYMBOL_HSI=HKEX:HSI1!
NEXT_PUBLIC_TV_SYMBOL_GOLD=COMEX:GC1!
NEXT_PUBLIC_TV_SYMBOL_OIL=NYMEX:CL1!
```

## 최소 동작 데모 시나리오

1. **회원가입**
   - `/signup` 접속
   - 필수 정보 입력 후 가입
   - 자동 로그인 및 `/app`으로 이동

2. **로그인**
   - `/login` 접속
   - 사용자명/비밀번호 입력
   - `/app`으로 이동

3. **Terminal 사용**
   - 차트 확인 (Member는 "15분 지연" 배지)
   - 채팅 참여 (Global 또는 종목별 채널)
   - 뉴스 확인 (한글화된 제목/요약)
   - 시그널 계산기 사용 (15분 이상 타임프레임)

4. **PRO 업그레이드 요청**
   - `/app/support` 접속
   - "업그레이드 요청" 버튼 클릭
   - 관리자에게 상담 요청

5. **Admin 승인**
   - Admin 계정으로 `/admin` 접속
   - 사용자 관리에서 해당 사용자 찾기
   - 권한을 "pro"로 변경

6. **PRO 기능 확인**
   - PRO로 로그인 후 `/app` 접속
   - 차트에 "LIVE" 배지 표시
   - 1분/5분 타임프레임 시그널 계산 가능

## 체크리스트

### 개발 환경
- [x] PostgreSQL 데이터베이스 설정
- [x] 백엔드 API 서버 실행
- [x] 프론트엔드 개발 서버 실행
- [x] Electron 개발 모드 실행

### 프로덕션 배포
- [ ] 백엔드 서버 배포 (예: AWS, Heroku, DigitalOcean)
- [ ] 프론트엔드 빌드 및 배포 (예: Vercel, Netlify)
- [ ] 데이터베이스 마이그레이션 실행
- [ ] 환경변수 설정
- [ ] SSL 인증서 설정 (HTTPS/WSS)

### Electron 배포
- [ ] 프론트엔드 프로덕션 빌드
- [ ] Electron 빌드 실행
- [ ] EXE 파일 테스트
- [ ] 코드 서명 (선택사항, 나중에)
- [ ] 자동 업데이트 설정 (선택사항, v2)

## 문제 해결

### 데이터베이스 연결 오류
- PostgreSQL 서비스가 실행 중인지 확인
- DATABASE_URL 환경변수 확인
- 데이터베이스가 생성되었는지 확인

### WebSocket 연결 실패
- 백엔드 서버가 실행 중인지 확인
- CORS 설정 확인
- 방화벽/프록시 설정 확인

### TradingView 차트 로드 실패
- 인터넷 연결 확인
- TradingView 심볼 문자열 확인 (환경변수)
- 브라우저 콘솔 오류 확인
