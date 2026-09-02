# Cloudflare Cron으로 스케줄 분리 (운영 안정성)

## 왜 분리하나요?

- **기존**: 서버(APScheduler) 안에서 20~30초 주기로 뉴스/지표/AI채팅 등 실행
- **문제**: 인스턴스가 2개만 있어도 작업이 2배 중복 실행 → 데이터 중복, API 쿼터 폭발, 비용·장애
- **해결**: **봉 완성 기준**으로 스케줄 트리거는 **Cloudflare Cron Worker가 단일**로 담당. 계산/수집 결과는 DB에 upsert되어 유저 수가 많아도 시스템이 안정적으로 버팀.

## 구조

```
[Cloudflare Cron Worker]  -- 매 1분 실행 (단일)
        │
        ├── 매 분:  POST /api/cron/news
        ├── 매 5분: POST /api/cron/indicators, /earnings, /calendar
        ├── 매 2분: POST /api/cron/ai-chat
        └── 매일 23:00 UTC (= 08:00 KST): POST /api/cron/investing-earnings
                │
                ▼
[백엔드 API]  CRON_SECRET 검증 후 해당 작업 1회만 실행
```

## 백엔드 설정

1. **환경 변수**
   - `CRON_SECRET`: Cron Worker만 알 수 있는 비밀값 (Cloudflare Secret과 동일하게 설정)
   - `DISABLE_IN_PROCESS_SCHEDULER=true`: **운영**에서는 반드시 설정 → 서버 내 APScheduler 비활성화

2. **로컬/개발**
   - `DISABLE_IN_PROCESS_SCHEDULER` 를 설정하지 않으면 기존처럼 서버 내 스케줄러가 동작 (30초/5분 등)
   - Cron Worker를 쓰지 않는 환경에서는 그대로 두면 됨

## Cloudflare Worker 배포

1. **디렉터리**
   ```bash
   cd cloudflare-cron
   ```

2. **시크릿 설정** (최초 1회)
   ```bash
   npx wrangler secret put CRON_SECRET   # 백엔드 CRON_SECRET과 동일한 값
   npx wrangler secret put BACKEND_URL   # 예: https://api.yourdomain.com
   ```

3. **배포**
   ```bash
   npx wrangler deploy
   ```

4. **Cron 스케줄**
   - `wrangler.toml` 에서 `crons = ["* * * * *"]` (매 1분). Worker 내부에서 시각 기준으로 5분/2분/매일 08:00 KST 분기.

## 스케줄 요약 (봉 완성 주기)

| 작업 | 주기 | Cron 분기 |
|------|------|------------|
| 뉴스 | 1분 | 매 분 |
| 지표 / 실적 / 캘린더 | 5분 | 분 % 5 == 0 |
| AI 랜덤 채팅 | 2분 | 분 % 2 == 0 |
| 인베스팅 오늘의 실적 | 매일 08:00 KST | 23:00 UTC, 분 0 |

## 시그널 계산과 D1 upsert (추가 확장)

- 현재 시그널은 **유저 요청 시** `/api/signals/calculate` 로 1회 계산·저장됩니다.
- **봉 완성 기준**으로 “심볼+타임프레임당 최신 1개”를 D1에 upsert하려면:
  - 백엔드에 `signal_cache` 같은 테이블 (symbol, timeframe, direction, ...) + Cron 전용 엔드포인트(예: `/api/cron/signal-d1`)를 추가하고,
  - Worker에서 1D 봉 마감 시점(예: 00:00 UTC)에 해당 엔드포인트를 호출하도록 확장하면 됩니다.
- 필요 시 해당 테이블·엔드포인트 설계부터 이어서 구현할 수 있습니다.
