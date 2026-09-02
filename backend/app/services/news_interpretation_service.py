"""
실시간 뉴스 해석: 뉴스 제목·요약을 받아 시장 관점의 해석 문단을 LLM으로 생성.
API 키는 환경 변수(LLM_API_KEY 등)로만 주입.
"""
import httpx
import os
from typing import Optional


def _load_api_config():
    api_key = os.getenv("LLM_API_KEY", "")
    api_url = os.getenv("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions")
    model = os.getenv("LLM_MODEL", "deepseek-chat")
    return api_key, api_url, model


# 뉴스 해석 전용 페르소나: 실시간 뉴스를 해석해 트레이더에게 알려주는 역할
NEWS_INTERPRETER_SYSTEM = """당신은 실시간 금융·시장 뉴스를 해석하는 전문가입니다.
주어진 뉴스의 핵심 내용, 시장에 미치는 영향(선물·주식·원유·금 등), 트레이더가 주의할 점을 2~4문장의 쉬운 한국어로 해석해 주세요.
과장하거나 투자 권유하지 말고, 사실과 맥락만 간결히 전달하세요. 다른 텍스트나 제목 없이 해석 문단만 반환하세요."""


async def interpret_news(title: str, summary: Optional[str] = None) -> Optional[str]:
    """
    뉴스 제목과 요약을 받아 해석 문단을 반환. API 키가 없거나 실패 시 None.
    """
    api_key, api_url, model = _load_api_config()
    if not api_key:
        return None

    text = title.strip()
    if summary and summary.strip():
        text = f"{text}\n\n{summary.strip()[:800]}"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                api_url,
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": NEWS_INTERPRETER_SYSTEM},
                        {"role": "user", "content": f"다음 뉴스를 해석해 주세요.\n\n{text}"},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 350,
                },
                timeout=25.0,
            )
            if response.status_code != 200:
                return None
            result = response.json()
            if "choices" not in result or not result["choices"]:
                return None
            content = result["choices"][0]["message"]["content"].strip()
            return content if content else None
    except Exception as e:
        print(f"[NEWS_INTERPRET] Error: {e}")
        return None
