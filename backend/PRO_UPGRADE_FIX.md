# PRO 업그레이드 신청 기능 수정 요약

## 문제
BASIC 유저가 `/app/pro-upgrade`에서 신청서를 제출하면 "요청 실패" 오류 발생

## 원인
- `pro.py`에서 `UserRole` import가 누락되어 있었음

## 수정 사항

### 1. backend/app/routers/pro.py

- `UserRole` import 추가
- 중복 신청 체크 로직 개선 (`pending`, `in_progress` 상태 모두 체크)
- 이미 진행 중인 상담 채팅이 있는지 확인
- `google_sheets_service` import 경로 수정
- 본인 상태 조회 API (`/my-status`) 추가

### 2. 프론트엔드 (변경 없음)
- 기존 코드가 이미 올바르게 구현되어 있음
- API 경로: `/api/pro/request-upgrade`
- 에러 처리: pending, Already PRO, Email/Phone 중복 등

## API 엔드포인트

| Method | Endpoint | 설명 |
|-------|----------|------|
| POST | `/api/pro/request-upgrade` | PRO 업그레이드 신청 |
| GET | `/api/pro/my-status` | 본인 신청 상태 조회 |

## 데이터 흐름

```
1. BASIC 유저가 pro-upgrade 페이지에서 폼 제출
2. 프론트엔드에서 /api/pro/request-upgrade 호출
3. 백엔드에서:
   - UserRole 체크 (PRO/ADMIN이면 에러)
   - pro_request_status 체크 (pending/in_progress면 에러)
   - 기존 상담 채팅 체크 (있으면 에러)
   - 이메일/전화번호 중복 체크
   - 사용자 정보 업데이트 (name, phone, email, pro_request_status)
   - SupportChat 생성 (status="pending", request_type="pro_upgrade")
   - 구글 시트 동기화 (비동기)
4. 성공 시 chat_id 반환
5. 프론트엔드에서 /app/support 페이지로 리다이렉트
```

## 관리자 페이지
- 기존 `/api/admin/support/inbox` API에서 PRO 업그레이드 신청(`request_type="pro_upgrade"`) 목록 확인 가능
- 관리자 페이지(`/admin`)에서 상담 관리 탭에서 신청 목록 확인 가능

## 테스트 방법

1. **백엔드 실행**
   ```bash
   cd backend
   .\venv\Scripts\python.exe main.py
   ```

2. **프론트엔드 실행**
   ```bash
   cd frontend
   npm run dev
   ```

3. **테스트 시나리오**
   - BASIC 유저로 로그인
   - `/app/pro-upgrade` 접속
   - 이름/전화번호/이메일 입력 후 제출
   - 성공 메시지 확인 및 `/app/support` 페이지로 이동 확인
   - 관리자 계정으로 로그인
   - `/admin` 접속 → 상담 관리 탭에서 신청 확인

4. **중복 신청 테스트**
   - 동일 계정으로 다시 `/app/pro-upgrade` 접속
   - "이미 진행 중인 PRO 업그레이드 상담이 있습니다" 메시지 확인
