import httpx
import os
import asyncio
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import News
from app.services.llm_provider import translate_and_summarize
from datetime import datetime
import re
from bs4 import BeautifulSoup
from typing import List, Optional

# Breaking 뉴스 키워드
BREAKING_KEYWORDS = [
    "breaking", "urgent", "alert", "emergency", "crisis",
    "crash", "surge", "plunge", "rally", "flash"
]

# 중요도 키워드
HIGH_IMPORTANCE_KEYWORDS = [
    "fed", "federal reserve", "interest rate", "inflation", "cpi",
    "gdp", "employment", "unemployment", "nfp", "non-farm payrolls"
]

YAHOO_RSS_URL = "https://finance.yahoo.com/rss/topstories"
BLOOMBERG_RSS_URL = "https://www.bloomberg.com/feeds/markets/news.rss"
REUTERS_MARKETS_URL = "https://www.reuters.com/markets/"
FINANCIAL_JUICE_URL = "https://www.financialjuice.com/home"
# Seeking Alpha 마켓 뉴스 (공식 RSS - /market-news 페이지와 동일 소스)
SEEKING_ALPHA_MARKET_NEWS_RSS = "https://seekingalpha.com/market_currents.xml"
# 뉴스정리 전용: Al Jazeera English
AL_JAZEERA_NEWS_RSS = "https://english.aljazeera.net/xml/rss/all.xml"

# Brotli 디코딩 오류 방지 (Windows/일부 환경)
COMMON_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Encoding": "gzip, deflate",
}

# 번역 작업 동시 실행 제한 (Render 무료 환경 고려 - 최대 2개 동시 실행)
_TRANSLATION_SEMAPHORE = asyncio.Semaphore(2)

async def fetch_yahoo_news() -> List[dict]:
    """Yahoo Finance RSS에서 뉴스 수집"""
    import feedparser
    news_items = []
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(YAHOO_RSS_URL, headers=COMMON_HEADERS)
            if response.status_code == 200:
                feed = feedparser.parse(response.text)
                for entry in feed.entries[:15]:
                    pub_at = datetime.utcnow()
                    if entry.get("published_parsed"):
                        try:
                            from time import mktime
                            pub_at = datetime.utcfromtimestamp(mktime(entry.published_parsed))
                        except Exception:
                            pass
                    news_items.append({
                        "title": entry.title,
                        "summary": entry.get("summary", ""),
                        "link": entry.link,
                        "source": "Yahoo Finance",
                        "published_at": pub_at
                    })
    except Exception as e: print(f"[NEWS] Yahoo RSS Error: {e}")
    return news_items

async def fetch_bloomberg_news() -> List[dict]:
    """Bloomberg RSS에서 뉴스 수집"""
    import feedparser
    news_items = []
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get("https://feeds.bloomberg.com/markets/news.rss", headers=COMMON_HEADERS)
            if response.status_code == 200:
                feed = feedparser.parse(response.text)
                for entry in feed.entries[:15]:
                    pub_at = datetime.utcnow()
                    if entry.get("published_parsed"):
                        try:
                            from time import mktime
                            pub_at = datetime.utcfromtimestamp(mktime(entry.published_parsed))
                        except Exception:
                            pass
                    news_items.append({
                        "title": entry.title,
                        "summary": entry.get("summary", ""),
                        "link": entry.link,
                        "source": "Bloomberg",
                        "published_at": pub_at
                    })
    except Exception as e: print(f"[NEWS] Bloomberg RSS Error: {e}")
    return news_items

async def fetch_reuters_news() -> List[dict]:
    """Reuters Markets 뉴스 수집 (모바일 사이트 시도 or API)"""
    news_items = []
    try:
        reuters_headers = {**COMMON_HEADERS, "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1"}
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(REUTERS_MARKETS_URL, headers=reuters_headers)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # Reuters often uses data-testid
                elements = soup.find_all('a', attrs={"data-testid": re.compile(r'Heading|Link', re.I)})
                for el in elements[:15]:
                    title = el.get_text(strip=True)
                    link = el.get('href', '')
                    if title and link and len(title) > 20:
                        if not link.startswith('http'): link = f"https://www.reuters.com{link}"
                        news_items.append({"title": title, "summary": "", "link": link, "source": "Reuters", "published_at": datetime.utcnow()})
    except Exception as e: print(f"[NEWS] Reuters Scrape Error: {e}")
    return news_items

async def fetch_financial_juice_news() -> List[dict]:
    """Financial Juice 뉴스 수집"""
    news_items = []
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(FINANCIAL_JUICE_URL, headers=COMMON_HEADERS)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # More generic link search
                for a in soup.find_all('a', href=re.compile(r'/news/|/article/')):
                    title = a.get_text(strip=True)
                    link = a['href']
                    if title and len(title) > 15:
                        if not link.startswith('http'): link = f"https://www.financialjuice.com{link}"
                        news_items.append({"title": title, "summary": "", "link": link, "source": "Financial Juice", "published_at": datetime.utcnow()})
                        if len(news_items) >= 15: break
    except Exception as e: print(f"[NEWS] Financial Juice Error: {e}")
    return news_items

async def fetch_seeking_alpha_news() -> List[dict]:
    """Seeking Alpha 마켓 뉴스 수집 (공식 RSS: market_currents = /market-news)"""
    import feedparser
    news_items = []
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(SEEKING_ALPHA_MARKET_NEWS_RSS, headers=COMMON_HEADERS)
            if response.status_code != 200:
                return news_items
            feed = feedparser.parse(response.text)
            for entry in feed.entries[:15]:
                title = (entry.get("title") or "").strip()
                link = entry.get("link") or ""
                summary = entry.get("summary", "") or ""
                if not title or not link:
                    continue
                if not link.startswith("http"):
                    link = f"https://seekingalpha.com{link}" if link.startswith("/") else f"https://seekingalpha.com/{link}"
                # published 파싱 (있으면 사용)
                pub_at = datetime.utcnow()
                if entry.get("published_parsed"):
                    try:
                        from time import mktime
                        pub_at = datetime.utcfromtimestamp(mktime(entry.published_parsed))
                    except Exception:
                        pass
                news_items.append({
                    "title": title,
                    "summary": summary[:500] if summary else "",
                    "link": link,
                    "source": "Seeking Alpha",
                    "published_at": pub_at,
                })
    except Exception as e:
        print(f"[NEWS] Seeking Alpha RSS Error: {e}")
    return news_items

async def fetch_aljazeera_news() -> List[dict]:
    """뉴스정리: Al Jazeera English 뉴스 (https://www.aljazeera.com/news/)"""
    import feedparser
    news_items = []
    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            response = await client.get(AL_JAZEERA_NEWS_RSS, headers=COMMON_HEADERS)
            if response.status_code != 200:
                return news_items
            feed = feedparser.parse(response.text)
            for entry in feed.entries[:20]:
                title = (entry.get("title") or "").strip()
                link = entry.get("link") or ""
                summary = entry.get("summary", "") or ""
                if not title or not link:
                    continue
                if not link.startswith("http"):
                    link = f"https://www.aljazeera.com{link}" if link.startswith("/") else f"https://www.aljazeera.com/{link}"
                pub_at = datetime.utcnow()
                if entry.get("published_parsed"):
                    try:
                        from time import mktime
                        pub_at = datetime.utcfromtimestamp(mktime(entry.published_parsed))
                    except Exception:
                        pass
                news_items.append({
                    "title": title,
                    "summary": summary[:500] if summary else "",
                    "link": link,
                    "source": "Al Jazeera",
                    "published_at": pub_at,
                })
    except Exception as e:
        print(f"[NEWS] Al Jazeera RSS Error: {e}")
    return news_items

def _broadcast_news(news: News):
    """뉴스 한 건을 WebSocket 채널 1로 브로드캐스트"""
    from app.websocket import manager
    import asyncio
    broadcast_data = {
        "type": "news",
        "id": news.id,
        "original_title": news.original_title,
        "ko_title": getattr(news, "ko_title", None),
        "ko_summary": getattr(news, "ko_summary", None),
        "original_link": news.original_link,
        "original_summary": news.original_summary,
        "is_breaking": news.is_breaking,
        "importance": news.importance,
        "sentiment": news.sentiment,
        "source": news.source,
        "created_at": news.created_at.isoformat() if news.created_at else None,
    }
    asyncio.create_task(manager.broadcast_to_channel(1, broadcast_data))


async def translate_news_in_background(news_id: int):
    """뉴스 번역을 백그라운드에서 수행하고 DB 갱신 후 브로드캐스트 (번역 완료 즉시 반영)
    동시 실행을 semaphore로 제한하여 LLM API 과부하 방지"""
    async with _TRANSLATION_SEMAPHORE:
        db = SessionLocal()
        try:
            news = db.query(News).filter(News.id == news_id).first()
            if not news:
                return
            try:
                ko_title, ko_summary = await translate_and_summarize(news.original_title, news.original_summary or "")
                news.ko_title = ko_title or news.original_title
                news.ko_summary = ko_summary or ""
                news.translated_at = datetime.utcnow()
                db.commit()
                db.refresh(news)
                _broadcast_news(news)
            except Exception as e:
                print(f"[NEWS] Translation error for news {news_id}: {e}")
                news.ko_title = news.original_title
                news.ko_summary = news.original_summary or ""
                db.commit()
                db.refresh(news)
                _broadcast_news(news)
        finally:
            db.close()


async def fetch_and_process_news():
    """뉴스 수집: 실시간 뉴스(로이터·블룸버그·야후) + 뉴스정리(Al Jazeera)"""
    db = SessionLocal()
    from app.services.llm_provider import analyze_sentiment
    import asyncio
    
    try:
        # 1. 실시간 뉴스: 로이터, 블룸버그, 야후파이낸스만
        tasks_realtime = [
            fetch_reuters_news(),
            fetch_bloomberg_news(),
            fetch_yahoo_news(),
        ]
        # 2. 뉴스정리: Al Jazeera (https://www.aljazeera.com/news/)
        tasks_breaking = [fetch_aljazeera_news()]
        results = await asyncio.gather(*tasks_realtime, *tasks_breaking)
        realtime_items = [item for sublist in results[:3] for item in sublist]
        aljazeera_items = results[3] if len(results) > 3 else []
        all_items = realtime_items + aljazeera_items
        
        new_count = 0
        for item in all_items:
            # 중복 체크 (Link 기준)
            existing = db.query(News).filter(News.original_link == item["link"]).first()
            if existing: continue
            
            # 1. Breaking/중요도 판단 (Al Jazeera = 뉴스정리용 high)
            title_lower = item["title"].lower()
            is_breaking = any(keyword in title_lower for keyword in BREAKING_KEYWORDS)
            importance = "normal"
            if item.get("source") == "Al Jazeera":
                importance = "high"  # 뉴스정리 패널에 항상 노출
            if is_breaking:
                importance = "critical"
            elif importance == "normal" and any(keyword in title_lower for keyword in HIGH_IMPORTANCE_KEYWORDS):
                importance = "high"
            
            # 2. Sentiment 분석
            try:
                sentiment = await analyze_sentiment(item["title"], item.get("summary", ""))
            except:
                sentiment = "neutral"

            # 3. 뉴스 저장 (원문만 저장, 번역은 비동기로 나중에)
            news = News(
                original_title=item["title"],
                original_summary=item.get("summary", "")[:500],
                original_link=item["link"],
                is_breaking=is_breaking,
                importance=importance,
                sentiment=sentiment,
                source=item.get("source", "Unknown"),
                published_at=item.get("published_at") or datetime.utcnow()
            )
            db.add(news)
            db.commit()
            db.refresh(news)

            # 4. 즉시 브로드캐스트 (원문으로 표시)
            try:
                _broadcast_news(news)
            except Exception as e:
                print(f"[NEWS] Broadcast error: {e}")
            # 5. 번역은 백그라운드에서 수행 후 DB 갱신 + 재브로드캐스트
            asyncio.create_task(translate_news_in_background(news.id))
            
            new_count += 1
        
        print(f"[NEWS] Fetched total {len(all_items)} items, added {new_count} new news items")
        
        # Finnhub 뉴스 (메인). GDELT는 429 이슈로 제외(필요 시 scheduler에서 낮은 빈도로 별도 호출).
        from app.services.finnhub_service import fetch_finnhub_news
        await fetch_finnhub_news()
                
    except Exception as e:
        print(f"[NEWS] Total Process Error: {e}")
        db.rollback()
    finally:
        db.close()
