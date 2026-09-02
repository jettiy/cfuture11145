# -*- coding: utf-8 -*-
"""
실시간 웹 검색 — @브리핑/채팅 시 이벤트·최신 뉴스 보강용.
FMP 수치 데이터와 병행해 GTC, 컨퍼런스, 최신 이슈 등 검색 결과를 LLM 컨텍스트에 주입.
"""
import asyncio
from typing import List, Optional

# 검색 트리거 키워드: 사용자 질문에 포함되면 웹 검색 병행
WEB_SEARCH_TRIGGER_KEYWORDS = [
    "gtc", "요약", "최신", "이벤트", "컨퍼런스", "발표", "키노트",
    "정리", "하이라이트", "요지", "개요", "무슨 내용", "어떤 내용",
]


def _sync_web_search(query: str, max_results: int = 5) -> List[dict]:
    """동기 웹 검색 (duckduckgo-search). 스레드에서 호출."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        return [{"title": r.get("title", ""), "body": r.get("body", ""), "href": r.get("href", "")} for r in results]
    except Exception as e:
        print(f"[WEB_SEARCH] Error: {e}")
        return []


async def get_web_search_for_briefing(user_message: str, symbol: str = "", max_results: int = 5) -> str:
    """
    사용자 질문이 이벤트/최신 뉴스 성격이면 웹 검색 실행 후 LLM용 텍스트 반환.
    트리거 키워드가 없으면 빈 문자열.
    """
    msg_lower = (user_message or "").strip().lower()
    if not any(kw in msg_lower or kw in (user_message or "") for kw in WEB_SEARCH_TRIGGER_KEYWORDS):
        return ""
    query = user_message.strip()[:100]
    if symbol:
        query = f"{symbol} {query}"
    results = await asyncio.to_thread(_sync_web_search, query, max_results)
    if not results:
        return ""
    lines = ["[실시간 웹 검색 결과]"]
    for i, r in enumerate(results, 1):
        title = (r.get("title") or "").strip()
        body = (r.get("body") or "").strip()[:300]
        if title or body:
            lines.append(f"{i}. {title}\n   {body}")
    return "\n".join(lines) if len(lines) > 1 else ""
