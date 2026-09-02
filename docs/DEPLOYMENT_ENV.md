# 배포 환경변수 가이드

## Vercel (프론트엔드)

| 환경변수 | 설명 | 예시 |
|----------|------|------|
| `NEXT_PUBLIC_API_BASE_URL` | 백엔드 API 주소 | `https://your-backend.onrender.com` |
| `NEXT_PUBLIC_WS_URL` | WebSocket 주소 (끝에 /ws 붙이지 말 것) | `wss://your-backend.onrender.com` |

---

## Render (백엔드)

| 환경변수 | 설명 | 예시 |
|----------|------|------|
| `DATABASE_URL` | PostgreSQL 연결 문자열 | `postgresql://user:pass@host:5432/db` |
| `SECRET_KEY` | JWT 서명용 시크릿 (32자 이상) | `your-secret-key-...` |
| `JWT_ALGORITHM` | JWT 알고리즘 | `HS256` |
| `JWT_EXPIRATION_HOURS` | 토큰 유효 시간(시간) | `24` |
| `LLM_API_KEY` | DeepSeek API 키 | `sk-...` |
| `LLM_API_URL` | LLM API 엔드포인트 | `https://api.deepseek.com/v1/chat/completions` |
| `LLM_MODEL` | LLM 모델명 | `deepseek-chat` |
| `FINNHUB_API_KEY` | Finnhub API 키 (뉴스/시세) | `...` |
| `CORS_ORIGINS` | 허용 프론트엔드 도메인 (쉼표 구분) | `https://your-app.vercel.app` |
| **`ADMIN_BOOTSTRAP_USERNAME`** | 서버 시작 시 이 username을 ADMIN으로 승격 | `admin` |

### ADMIN_BOOTSTRAP_USERNAME (관리자 자동 승격)

- **용도**: Render 무료 플랜 등 Shell 없이 관리자 계정 유지
- **동작**: 서버 시작 시 한 번만 실행. 해당 username이 DB에 있으면 role을 ADMIN으로 업데이트
- **설정 예시**: `ADMIN_BOOTSTRAP_USERNAME=admin`
- **사전 조건**: `admin` username으로 회원가입된 계정이 있어야 함
- **로그**:
  - `[ADMIN_BOOTSTRAP] Promoted user to ADMIN: admin` — 승격 완료
  - `[ADMIN_BOOTSTRAP] User already ADMIN: admin` — 이미 ADMIN
  - `[ADMIN_BOOTSTRAP] User not found (no change): admin` — 해당 계정 없음
- **보안**: 관리자 승격 후 환경변수 제거 시 다음 배포부터 실행되지 않음

---

## 재배포 후 체크포인트

1. **백엔드 (Render)**
   - [ ] 서버 로그에 `[OK] Database tables created successfully` 출력
   - [ ] `ADMIN_BOOTSTRAP_USERNAME` 설정 시 `[ADMIN_BOOTSTRAP] Promoted user to ADMIN: admin` 또는 `User already ADMIN` 로그 확인
   - [ ] `/health` 응답 200
   - [ ] `/api/auth/login` 로그인 가능

2. **프론트엔드 (Vercel)**
   - [ ] 로그인 후 메인 화면 로드
   - [ ] 우측 상단 시계가 KST(한국 시간)로 표시
   - [ ] 채팅 메시지 시간이 KST로 표시
   - [ ] 최근 시그널 시간이 KST로 표시
   - [ ] 뉴스 시간이 KST로 표시

3. **관리자**
   - [ ] `admin` 계정으로 로그인 후 `/admin` 접근 가능
   - [ ] 사용자 관리, 상담 관리 탭 동작
