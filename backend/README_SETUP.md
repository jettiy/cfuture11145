# 백엔드 서버 설정 및 실행 가이드

## 1. 가상환경 활성화

```powershell
cd backend
.\venv\Scripts\activate
```

## 2. 데이터베이스 초기화 (최초 1회)

```powershell
python app/init_db.py
```

## 3. 관리자 계정 생성 (선택사항)

```powershell
python create_admin.py
```

기본 관리자 계정:
- 아이디: `aaaa`
- 비밀번호: `1234`
- 닉네임: `관리자`

## 4. 백엔드 서버 실행

```powershell
python main.py
```

서버가 `http://localhost:8000`에서 실행됩니다.

## 5. 확인

브라우저에서 `http://localhost:8000/health` 접속 시 `{"status": "ok"}` 응답이 오면 정상 작동 중입니다.

## 문제 해결

### 데이터베이스 에러 발생 시
1. `futures_terminal.db` 파일 삭제
2. `python app/init_db.py` 실행하여 재생성
3. 서버 재시작

### 포트 충돌 시
- `main.py`의 포트 번호 변경 (기본: 8000)
