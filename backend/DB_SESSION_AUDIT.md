# DB 세션 점검 요약 (QueuePool Timeout 대응)

## 1. 적용된 수정 사항

### `backend/app/database.py`
- **pool_pre_ping=True**: stale 연결 방지 (Render 등 장시간 idle 시 끊긴 연결 재검증)
- **pool_size=2**: Render 소형 환경에 맞게 기본 풀 크기 축소 (기본 5 → 2)
- **max_overflow=5**: 최대 오버플로우 연결 수 (기본 10 → 5)
- **pool_recycle=300**: 5분마다 연결 재활용 (장시간 idle 연결 정리)

## 2. 세션 close 점검 결과

| 파일 | 함수/위치 | SessionLocal 사용 | close 여부 |
|------|-----------|------------------|------------|
| `main.py` | ADMIN_BOOTSTRAP | `db = SessionLocal()` | ✅ `finally: db.close()` |
| `database.py` | `get_db` (Depends) | `db = SessionLocal()` | ✅ `yield` 후 `finally: db.close()` |
| `news_service.py` | `translate_news_in_background` | `db = SessionLocal()` | ✅ `finally: db.close()` |
| `news_service.py` | `fetch_and_process_news` | `db = SessionLocal()` | ✅ `finally: db.close()` |
| `finnhub_service.py` | `fetch_finnhub_news` | `db = SessionLocal()` | ✅ `finally: db.close()` |
| `finnhub_service.py` | `fetch_finnhub_economic_data` | `db = SessionLocal()` | ✅ `finally: db.close()` |
| `finnhub_service.py` | `fetch_finnhub_earnings` | `db = SessionLocal()` | ✅ `finally: db.close()` |
| `gdelt_service.py` | `fetch_gdelt_news` | `db = SessionLocal()` | ✅ `finally: db.close()` |
| `indicators_service.py` | `fetch_economic_indicators` | `db = SessionLocal()` | ✅ `finally: db.close()` |
| `indicators_service.py` | `fetch_earnings` | `db = SessionLocal()` | ✅ `finally: db.close()` |
| `calendar_service.py` | `fetch_economic_calendar` | `db = SessionLocal()` | ✅ `finally: db.close()` |
| `ai_chat_service.py` | `handle_briefing_analyst` | `db = SessionLocal()` | ✅ `finally: db.close()` |
| `ai_chat_service.py` | `trigger_random_ai_chat` | `db = SessionLocal()` | ✅ `finally: db.close()` |
| `ai_chat_service.py` | `handle_ai_response` | `db = SessionLocal()` | ✅ `finally: db.close()` |
| `signal_analysis_service.py` | `analyze_signal_with_llm` | `db = SessionLocal()` (db=None일 때) | ✅ `finally: if close_db: db.close()` |
| `investing_earnings_service.py` | `fetch_investing_earnings_today` | `db = SessionLocal()` | ✅ `finally: db.close()` |
| `websocket.py` | `websocket_endpoint` | `db = SessionLocal()` | ✅ `finally: db.close()` |
| `init_db.py` | `init_db` | `db = SessionLocal()` | ✅ `finally: db.close()` |
| `create_admin.py` | `ensure_admin` | `db = SessionLocal()` | ✅ `finally: db.close()` |

## 3. 세션 close 누락 파일

**없음.** 모든 `SessionLocal()` 사용처에서 `try/finally` 또는 `get_db`의 `yield` 후 `finally`로 세션이 정상적으로 닫히고 있음.

## 4. Pool 설정 변경 요약

| 항목 | 변경 전 (기본값) | 변경 후 |
|------|------------------|---------|
| pool_pre_ping | False | **True** |
| pool_size | 5 | **2** |
| max_overflow | 10 | **5** |
| pool_recycle | -1 (무제한) | **300** (5분) |

## 5. 권장 사항

- Render 재배포 후 모니터링하여 `QueuePool limit reached` 오류 재발 여부 확인
- 동시 요청/백그라운드 태스크가 많을 경우 `pool_size`/`max_overflow`를 소폭 상향 검토 가능
- `translate_news_in_background`, `handle_briefing_analyst` 등 `asyncio.create_task`로 생성되는 태스크는 각자 독립 세션을 사용하므로, 동시 다수 실행 시 pool 사용량이 일시적으로 증가할 수 있음. 현재 설정으로 대부분 완화됨.
