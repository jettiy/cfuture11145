"""
GDELT API를 사용한 글로벌 뉴스 이벤트 데이터 수집
429 회피: 호출 빈도 감소, backoff, 캐시(최소 호출 간격).
"""
import httpx
import os
import asyncio
import time
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import News
from app.services.llm_provider import translate_and_summarize
from datetime import datetime, timedelta, timezone
from typing import List, Optional
import json

GDELT_QUERY_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
# 429 방지: 최소 호출 간격(초). 10분으로 늘려 API 호출 빈도 줄임
GDELT_MIN_INTERVAL_SEC = 600  # 10분
_LAST_GDELT_FETCH_TIME: float = 0.0
_GDELT_MAX_RETRIES = 3
_GDELT_BACKOFF_BASE_SEC = 60


async def fetch_gdelt_news():
    """GDELT에서 글로벌 뉴스 이벤트 수집. 호출 빈도 제한 + 429 시 backoff."""
    global _LAST_GDELT_FETCH_TIME
    now = time.time()
    if now - _LAST_GDELT_FETCH_TIME < GDELT_MIN_INTERVAL_SEC:
        return
    db = SessionLocal()
    try:
        query = "financial OR economic OR stock OR market OR trading OR futures"
        timespan = "1d"
        params = {
            "query": query,
            "mode": "artlist",
            "maxrecords": 15,
            "format": "json",
            "timespan": timespan
        }
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = None
            for attempt in range(_GDELT_MAX_RETRIES):
                try:
                    resp = await client.get(GDELT_QUERY_URL, params=params)
                    if resp.status_code == 429:
                        wait = _GDELT_BACKOFF_BASE_SEC * (2 ** attempt)
                        print(f"[GDELT] 429 Too Many Requests, backoff {wait}s (attempt {attempt + 1}/{_GDELT_MAX_RETRIES})")
                        await asyncio.sleep(wait)
                        continue
                    resp.raise_for_status()
                    response = resp
                    _LAST_GDELT_FETCH_TIME = time.time()
                    break
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429 and attempt < _GDELT_MAX_RETRIES - 1:
                        wait = _GDELT_BACKOFF_BASE_SEC * (2 ** attempt)
                        await asyncio.sleep(wait)
                        continue
                    raise
            if response is None:
                return

            try:
                content_type = response.headers.get('content-type', '')
                if 'json' in content_type:
                    data = response.json()
                else:
                    # 텍스트 형식일 수 있음
                    text = response.text
                    try:
                        data = json.loads(text)
                    except:
                        # CSV나 다른 형식일 수 있음
                        print(f"[GDELT] Unexpected response format: {content_type}")
                        return
                
                # 응답 구조 확인 (articles 또는 다른 키)
                articles = []
                if isinstance(data, list):
                    articles = data
                elif isinstance(data, dict):
                    articles = data.get('articles', []) or data.get('results', []) or data.get('data', [])
                
                for article in articles:
                    # GDELT 응답 형식에 맞게 필드 추출
                    url = article.get('url', '') or article.get('ArticleURL', '') or article.get('url_mobile', '')
                    title = article.get('title', '') or article.get('Title', '') or article.get('title_en', '')
                    snippet = article.get('snippet', '') or article.get('Snippet', '') or article.get('summary', '')
                    
                    if not url or not title:
                        continue
                    
                    # 중복 체크
                    existing = db.query(News).filter(
                        News.original_link == url
                    ).first()
                    if existing:
                        continue
                    
                    # Breaking/중요도 판단
                    title_lower = title.lower()
                    is_breaking = any(keyword in title_lower for keyword in [
                        "breaking", "urgent", "alert", "emergency", "crisis",
                        "crash", "surge", "plunge", "rally", "flash"
                    ])
                    importance = "normal"
                    if is_breaking:
                        importance = "critical"
                    elif any(keyword in title_lower for keyword in [
                        "fed", "federal reserve", "interest rate", "inflation", "cpi",
                        "gdp", "employment", "unemployment", "nfp"
                    ]):
                        importance = "high"
                    
                    # 발행 시간 파싱
                    published_at = datetime.utcnow()
                    date_str = article.get('seendate', '') or article.get('Date', '') or article.get('datetime', '')
                    if date_str:
                        try:
                            if isinstance(date_str, (int, float)):
                                published_at = datetime.fromtimestamp(date_str, tz=timezone.utc)
                            else:
                                # 문자열 형식 파싱
                                published_at = datetime.fromisoformat(str(date_str).replace('Z', '+00:00'))
                        except:
                            pass
                    
                    # 뉴스 저장
                    news = News(
                        original_title=title,
                        original_summary=snippet[:500] if snippet else "",
                        original_link=url,
                        is_breaking=is_breaking,
                        importance=importance,
                        source="GDELT",
                        published_at=published_at
                    )
                    db.add(news)
                    db.commit()
                    db.refresh(news)
                    
                    # 번역 및 요약 - 항상 한글 필드 채우기
                    try:
                        ko_title, ko_summary = await translate_and_summarize(
                            news.original_title,
                            news.original_summary or ""
                        )
                        # 번역 결과가 있으면 저장, 없어도 원문이라도 저장
                        if ko_title:
                            news.ko_title = ko_title
                        if ko_summary:
                            news.ko_summary = ko_summary
                        news.translated_at = datetime.utcnow()
                        db.commit()
                    except Exception as e:
                        print(f"Translation error for news {news.id}: {e}")
                        # 번역 실패해도 원문이라도 한글 필드에 저장
                        if not news.ko_title:
                            news.ko_title = news.original_title
                        if not news.ko_summary:
                            news.ko_summary = news.original_summary or news.original_title[:200]
                        db.commit()
                
                print(f"[GDELT] Fetched {len(articles)} news items from GDELT")
                
            except httpx.HTTPError as e:
                print(f"[GDELT] HTTP error: {e}")
            except json.JSONDecodeError as e:
                print(f"[GDELT] JSON decode error: {e}")
            except Exception as e:
                print(f"[GDELT] Error: {e}")
                import traceback
                traceback.print_exc()
        
    except Exception as e:
        print(f"[GDELT] Error: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
    finally:
        db.close()
