# 서비스 구조 안정화 요약

## 목표

- 무료/비공식 데이터 소스 의존도 감소, 정식 API 중심 구조
- yfinance / GDELT rate limit 완화
- 뉴스 번역 지연 감소 및 실시간 반영
- 실시간 채팅 정상화 및 채팅 히스토리 표시

---

## 1. WebSocket URL 조합 (기존 적용 유지)

- **파일**: `frontend/lib/websocket.ts`
- **내용**: `getWebSocketBaseUrl()`로 base URL 끝의 `/ws` 제거 후 한 번만 붙여 `/ws/ws/chat/...` 방지.
- **채팅 연결 실패 로그**: `[WS] Closed ... code= reason= url=` 형태로 원인 추적 가능.

---

## 2. 채팅 히스토리

- **백엔드**: `GET /api/chat/channels/{channel_id}/messages?limit=50` (기존) + **인증 필수** (`get_current_active_user`).
- **프론트**: `ChatPanel`에서 채널 선택 시 `chatAPI.getMessages(currentChannel.id, 50)` 호출 후 `setMessages(list)`.
- **결과**: 입장 시 최근 50건 히스토리 표시, 이후 WebSocket으로 실시간 메시지 추가.

---

## 3. 차트 데이터: Finnhub 우선, yfinance fallback

- **파일**  
  - `backend/app/services/finnhub_service.py`: `fetch_finnhub_candles(symbol, timeframe, period_days)` 추가.  
  - `backend/app/services/chart_data_service.py`: 1) Finnhub 시도 → 2) 실패/미지원 시 yfinance.
- **Finnhub 캔들**: `FINNHUB_CANDLE_SYMBOL_MAP`에 있는 심볼만 사용 (선물 NQ1! 등은 미등록 → yfinance 사용).
- **효과**: 정식 API(Finnhub) 우선, yfinance는 보조로만 사용해 rate limit 영향 축소.

---

## 4. GDELT 제거

- **파일**: `backend/app/services/news_service.py`
- **변경**: `fetch_and_process_news()` 내부에서 `fetch_gdelt_news()` 호출 제거. Finnhub 뉴스만 사용.
- **GDELT 코드**: `gdelt_service.py`는 유지. 필요 시 스케줄러에서 낮은 빈도(예: 1일 1회)로 별도 호출 가능.

---

## 5. 뉴스 캐시

- **파일**: `backend/app/routers/news.py`
- **내용**: `GET /api/news` 응답을 메모리 캐시 (`_NEWS_LIST_CACHE`), TTL 20초.
- **효과**: 동일 클라이언트/다중 요청 시 DB 부하 감소.

---

## 6. 뉴스 번역 비동기 + 즉시 반영

- **저장 흐름**  
  1. 뉴스 원문만 DB 저장 (ko_title/ko_summary는 null 가능).  
  2. 저장 직후 WebSocket으로 브로드캐스트 → 프론트는 원문으로 바로 표시.  
  3. `asyncio.create_task(translate_news_in_background(news.id))`로 번역 비동기 실행.
- **백그라운드 번역** (`news_service.translate_news_in_background(news_id)`):  
  - DB에서 해당 뉴스 조회 → `translate_and_summarize` 호출 → ko_title/ko_summary/translated_at 갱신 후 commit.  
  - 동일 뉴스로 다시 브로드캐스트.
- **적용 위치**: `news_service.fetch_and_process_news`, `finnhub_service.fetch_finnhub_news` (저장 후 브로드캐스트 + `translate_news_in_background` 태스크).
- **프론트**: `NewsPanel`의 `news_update` 수신 시, 기존 id가 있으면 해당 항목만 갱신(번역 필드 반영), 없으면 새로 추가. 번역 완료 시 별도 폴링 없이 WebSocket만으로 즉시 반영.

---

## 7. 변경/추가된 파일 목록

| 구분 | 파일 | 변경 요약 |
|------|------|-----------|
| 프론트 | `frontend/lib/websocket.ts` | WS base URL 정규화, 연결 실패 로그 (기존 유지) |
| 프론트 | `frontend/components/ChatPanel.tsx` | 채널별 히스토리 로드 `chatAPI.getMessages()` |
| 프론트 | `frontend/components/NewsPanel.tsx` | `news_update` 시 기존 id면 항목 갱신(번역 즉시 반영) |
| 백엔드 | `backend/app/routers/chat.py` | `get_messages`에 `get_current_active_user` 의존 추가 |
| 백엔드 | `backend/app/routers/news.py` | 뉴스 목록 캐시 (TTL 20초) |
| 백엔드 | `backend/app/services/news_service.py` | 뉴스 저장 후 즉시 브로드캐스트 + `translate_news_in_background` 태스크, GDELT 호출 제거 |
| 백엔드 | `backend/app/services/finnhub_service.py` | `fetch_finnhub_candles` 추가, 뉴스 저장 후 비동기 번역 태스크 |
| 백엔드 | `backend/app/services/chart_data_service.py` | Finnhub 캔들 1차 시도, yfinance fallback |
| 문서 | `docs/ARCHITECTURE_STABILITY.md` | 본 구조/변경 요약 |

---

## 8. 데이터 소스 정리

| 용도 | 메인 | 보조/비고 |
|------|------|-----------|
| 뉴스 | Finnhub, RSS(로이터·블룸버그·야후·Al Jazeera) | GDELT 제거(선택 시 낮은 빈도 별도 작업) |
| 차트/시세 | Finnhub (지원 심볼만) | yfinance fallback (선물 등) |
| 채팅 | 자체 DB + WebSocket | 히스토리 REST + 실시간 WS |

---

## 9. 배포 후 기대 효과

- WebSocket 403/경로 오류: URL 정규화로 `/ws/ws` 중복 제거, 로그로 원인 파악 용이.
- 채팅: 히스토리 API + 인증으로 기존 대화 표시, 실시간 메시지 유지.
- yfinance: Finnhub 우선 사용으로 rate limit 완화, yfinance는 보조만 사용.
- GDELT: 메인 플로우 제거로 429 감소.
- 뉴스 번역: 원문 즉시 표시 → 백그라운드 번역 → 완료 시 WebSocket으로 즉시 반영.
- 뉴스 API: 20초 캐시로 반복 요청 시 DB 부하 감소.
