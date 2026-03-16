import os
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from app.services.news_service import fetch_and_process_news
from app.services.indicators_service import fetch_economic_indicators, fetch_earnings
from app.services.calendar_service import fetch_economic_calendar
from app.services.investing_earnings_service import fetch_investing_earnings_today

# 환경 변수는 Cloudflare Secrets / 시스템 환경변수로만 주입
# DISABLE_IN_PROCESS_SCHEDULER=true 이면 스케줄러 미시작 (Cloudflare Cron 단일 실행)

# Render 무료 환경에 맞춘 보수적인 수집 주기
NEWS_FETCH_INTERVAL_MINUTES = int(os.getenv("NEWS_FETCH_INTERVAL_MINUTES", "10"))  # 기본 10분
INDICATORS_FETCH_INTERVAL_MINUTES = int(os.getenv("INDICATORS_FETCH_INTERVAL_MINUTES", "15"))  # 기본 15분

scheduler = AsyncIOScheduler()

def start_scheduler():
    if os.getenv("DISABLE_IN_PROCESS_SCHEDULER", "").lower() in ("1", "true", "yes"):
        return
    # 뉴스 수집 스케줄러 (10분마다 - API 호출 빈도 줄임)
    scheduler.add_job(
        fetch_and_process_news,
        trigger=IntervalTrigger(minutes=NEWS_FETCH_INTERVAL_MINUTES),
        id="fetch_news",
        replace_existing=True
    )

    # 지표/실적/캘린더 업데이트 (15분마다 - 스크래핑 빈도 줄임)
    scheduler.add_job(
        fetch_economic_indicators,
        trigger=IntervalTrigger(minutes=INDICATORS_FETCH_INTERVAL_MINUTES),
        id="fetch_indicators_interval",
        replace_existing=True
    )

    scheduler.add_job(
        fetch_earnings,
        trigger=IntervalTrigger(minutes=INDICATORS_FETCH_INTERVAL_MINUTES),
        id="fetch_earnings_interval",
        replace_existing=True
    )

    scheduler.add_job(
        fetch_economic_calendar,
        trigger=IntervalTrigger(minutes=INDICATORS_FETCH_INTERVAL_MINUTES),
        id="fetch_calendar_interval",
        replace_existing=True
    )

    # (AI 페르소나 자동 채팅 제거됨 - 뉴스 해석 페르소나로 대체)

    # 매일 오전 8시(KST) 지표·캘린더·실적 갱신 (인베스팅닷컴 기준)
    scheduler.add_job(
        fetch_economic_indicators,
        trigger=CronTrigger(hour=8, minute=0, timezone='Asia/Seoul'),
        id="daily_indicator_reset",
        replace_existing=True
    )
    scheduler.add_job(
        fetch_economic_calendar,
        trigger=CronTrigger(hour=8, minute=0, timezone='Asia/Seoul'),
        id="daily_calendar_reset",
        replace_existing=True
    )

    # 매일 08:00 KST 인베스팅닷컴 실적 캘린더 갱신 (오늘의 실적)
    scheduler.add_job(
        fetch_investing_earnings_today,
        trigger=CronTrigger(hour=8, minute=0, timezone='Asia/Seoul'),
        id="daily_investing_earnings",
        replace_existing=True
    )
    
    scheduler.start()
    print(f"[SCHEDULER] Started with conservative intervals: News={NEWS_FETCH_INTERVAL_MINUTES}min, Indicators={INDICATORS_FETCH_INTERVAL_MINUTES}min")
    
    # 서버 시작 시 즉시 실행 (초기 데이터 수집) - 별도 스레드에서 실행
    import threading
    def init_fetch():
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        # 뉴스는 즉시 수집
        loop.run_until_complete(fetch_and_process_news())
        # 지표/실적/캘린더도 즉시 수집 (오늘 데이터)
        loop.run_until_complete(fetch_economic_indicators())
        loop.run_until_complete(fetch_earnings())
        loop.run_until_complete(fetch_investing_earnings_today())  # 오늘의 실적 (인베스팅)
        loop.run_until_complete(fetch_economic_calendar())
        loop.close()
    
    thread = threading.Thread(target=init_fetch, daemon=True)
    thread.start()

def shutdown_scheduler():
    try:
        if scheduler.running:
            scheduler.shutdown()
    except Exception:
        pass
