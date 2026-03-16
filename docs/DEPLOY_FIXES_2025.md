# 배포 이슈 수정 요약 (2025)

## 수정한 파일

| 파일 | 변경 내용 |
|------|-----------|
| `frontend/lib/websocket.ts` | WebSocket base URL에서 `/ws` 중복 제거, 연결 실패 시 URL·code·reason 로그 |
| `frontend/components/ChatPanel.tsx` | WebSocket 연결 실패 시 채널 정보·fallback 안내 로그 |
| `frontend/components/NewsPanel.tsx` | 뉴스 원문 먼저 표시, 번역 도착 시 한글로 교체, "(번역 중)" 표시 |
| `backend/app/services/chart_data_service.py` | yfinance 캐시(TTL 90초), 요청 간격 2초, 429/실패 시 재시도(최대 3회) |
| `backend/app/services/gdelt_service.py` | GDELT 호출 간격 5분, 429 시 exponential backoff 재시도 |
| `backend/app/services/signal_analysis_service.py` | 차트 데이터 실패 시 최대 3회 재시도(2·4초 대기) |

## 배포 후 기대 효과

1. **WebSocket 403 / 실시간 채팅**  
   - `NEXT_PUBLIC_WS_URL`이 `.../ws`로 끝나도 `/ws/ws/chat/...`가 되지 않도록 정규화.  
   - 채팅 연결 실패 시 콘솔에 URL·close code(1006 등)·reason이 찍혀 원인 파악이 쉬움.

2. **뉴스 "번역 준비 중" 장시간 노출**  
   - 제목/요약을 원문(영문)으로 먼저 보여주고, 번역 완료 시 한글로 교체.  
   - "(번역 중)" 표시로 번역 대기 중임을 명확히 표시.

3. **yfinance Too Many Requests**  
   - 동일 심볼·타임프레임은 90초 캐시 사용.  
   - 심볼별 최소 2초 간격, 429/에러 시 최대 3회 재시도로 429 발생 및 실패 감소.

4. **GDELT 429 Too Many Requests**  
   - GDELT 호출을 최소 5분 간격으로 제한.  
   - 429 수신 시 60초→120초→240초 backoff 재시도.

5. **시그널 계산 시 차트 데이터 실패**  
   - `fetch_chart_data` 내부 재시도 + 시그널 분석 단에서 차트 실패 시 최대 3회 재시도.  
   - 일시적 네트워크/rate limit에서도 시그널 계산 성공 가능성 증가.
