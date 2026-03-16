"""
저수지 패턴: FMP에서만 데이터 수집 → DB Upsert. 프론트는 DB만 조회.
- fetch_fmp_calendar: 15분마다 (미국 경제 캘린더)
- fetch_fmp_news: 5분마다 (시장 뉴스)
- fetch_fmp_indexes: 1분마다 (주요 지수)
- 지표 발표 전후 5분: 10초 단위 FMP 폴링 + actual 업데이트 시 웹소켓 알림
"""
import asyncio
import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.database import SessionLocal
from app.services.calendar_service import fetch_economic_calendar, has_events_in_realtime_window
from app.services.fmp_service import fetch_fmp_news, fetch_fmp_indexes
from app.websocket import manager

# DISABLE_IN_PROCESS_SCHEDULER=true 이면 스케줄러 미시작 (Cloudflare Cron 등 외부 트리거 시)
# 지표 발표 전후 이 시간(초)마다 FMP 체크 (발표 시간 근처에서만)
INDICATOR_REALTIME_POLL_SECONDS = 10
INDICATOR_IDLE_SLEEP_SECONDS = 60

scheduler = AsyncIOScheduler()


async def _fetch_calendar_return_count():
    """15분 주기 job용: fetch_economic_calendar는 (count, updated_events) 반환."""
    await fetch_economic_calendar()


async def run_indicator_realtime_poll_loop():
    """
    발표 예정 시간(scheduled_time) 전후 5분 구간에 있는 이벤트가 있으면
    10초마다 FMP 캘린더를 조회해 actual 값을 실시간 반영하고,
    actual이 갱신되면 웹소켓으로 모든 연결에 알림.
    """
    print("[SCHEDULER] Indicator realtime poll loop started (10s near release, 60s idle)")
    while True:
        try:
            db = SessionLocal()
            try:
                in_window = has_events_in_realtime_window(db)
            finally:
                db.close()
            if in_window:
                _, updated_events = await fetch_economic_calendar()
                if updated_events:
                    await manager.broadcast_to_all({
                        "type": "indicator_actual_updated",
                        "events": updated_events,
                    })
                    print(f"[SCHEDULER] Broadcast indicator_actual_updated: {len(updated_events)} events")
            sleep_sec = INDICATOR_REALTIME_POLL_SECONDS if in_window else INDICATOR_IDLE_SLEEP_SECONDS
        except Exception as e:
            print(f"[SCHEDULER] Indicator realtime poll error: {e}")
            sleep_sec = INDICATOR_IDLE_SLEEP_SECONDS
        await asyncio.sleep(sleep_sec)


def start_scheduler():
    if os.getenv("DISABLE_IN_PROCESS_SCHEDULER", "").lower() in ("1", "true", "yes"):
        print("[SCHEDULER] Disabled (DISABLE_IN_PROCESS_SCHEDULER)")
        return

    # 15분마다: 미국 경제 캘린더 (FMP stable/economic-calendar → DB)
    scheduler.add_job(
        _fetch_calendar_return_count,
        trigger=IntervalTrigger(minutes=15),
        id="fetch_fmp_calendar",
        replace_existing=True,
    )
    # 5분마다: 시장 뉴스 (FMP api/v3/fmp/articles → DB)
    scheduler.add_job(
        fetch_fmp_news,
        trigger=IntervalTrigger(minutes=5),
        id="fetch_fmp_news",
        replace_existing=True,
    )
    # 1분마다: 주요 지수 (FMP api/v3/quote → DB)
    scheduler.add_job(
        fetch_fmp_indexes,
        trigger=IntervalTrigger(minutes=1),
        id="fetch_fmp_indexes",
        replace_existing=True,
    )

    scheduler.start()
    # 지표 발표 전후 5분 구간 10초 폴링 + actual 업데이트 시 웹소켓 알림 (별도 이벤트 루프 태스크)
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(run_indicator_realtime_poll_loop())
    except RuntimeError:
        pass  # 이벤트 루프 없음(테스트 등) 시 스킵
    print("[SCHEDULER] Started: FMP calendar=15min, news=5min, indexes=1min; indicator realtime 10s near release")


def shutdown_scheduler():
    try:
        if scheduler.running:
            scheduler.shutdown()
    except Exception:
        pass
