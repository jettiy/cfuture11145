import httpx
import os

"""
API 키는 환경 변수(Cloudflare Secrets 등)로만 주입합니다. .env 파일 직접 읽기 및 키 로그 금지.
"""


def _load_api_config():
    """환경 변수에서만 API 설정 로드 (Cloudflare Secrets / 시스템 환경변수)"""
    api_key = os.getenv("LLM_API_KEY", "")
    api_url = os.getenv("LLM_API_URL", "https://api.deepseek.com/v1/chat/completions")
    model = os.getenv("LLM_MODEL", "deepseek-chat")
    return api_key, api_url, model

# 초기 로드 (모듈 임포트 시)
LLM_API_KEY, LLM_API_URL, LLM_MODEL = _load_api_config()

async def translate_and_summarize(title: str, summary: str = "") -> tuple[str, str]:
    """
    LLM을 사용하여 제목과 요약을 한국어로 번역하고 요약
    추상화된 인터페이스로 구현하여 나중에 모델을 변경할 수 있음
    """
    # 런타임에 최신 API 설정 로드
    current_api_key, current_api_url, current_model = _load_api_config()
    
    if not current_api_key:
        # API 키가 없으면 기본 번역 제공 (원문 그대로 표시하되 한글 필드에 저장)
        # 최소한 한글이 표시되도록 원문을 한글 필드에 넣음
        ko_title = title  # 원문을 그대로 사용 (나중에 번역 가능)
        ko_summary = summary[:500] if summary else title[:200]  # 요약이 없으면 제목 사용
        return ko_title, ko_summary
    
    try:
        async with httpx.AsyncClient() as client:
            # 제목 번역
            # DeepSeek API 헤더 설정
            headers = {
                "Authorization": f"Bearer {current_api_key}",
                "Content-Type": "application/json"
            }
            title_response = await client.post(
                current_api_url,
                headers=headers,
                json={
                    "model": current_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a professional translator specializing in financial news. Translate the following English financial news title to natural Korean. Rules:\n1. Return only the translated Korean title.\n2. No prefixes, explanations, or brackets.\n3. If the title starts with 'Source: ...' or 'Axios reports...', translate it as 'Axios가 보도: ...' or '...라고 Axios가 보도' to sound like a professional Korean news header.\n4. Keep it concise."
                        },
                        {
                            "role": "user",
                            "content": title
                        }
                    ],
                    "temperature": 0.3
                },
                timeout=30.0
            )
            
            # HTTP 상태 코드 확인
            title_response.raise_for_status()
            title_data = title_response.json()
            
            # 응답 구조 검증
            if "choices" not in title_data or not title_data["choices"]:
                error_msg = title_data.get("error", {}).get("message", "Unknown error") if "error" in title_data else "No choices in response"
                raise ValueError(f"LLM API 응답 오류: {error_msg}")
            
            # 요약 번역 및 3줄 요약
            summary_response = await client.post(
                current_api_url,
                headers=headers,
                json={
                    "model": current_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a professional translator and summarizer specializing in financial news. Translate the following English financial news content to natural Korean and summarize it in exactly 3 lines. Each line should be a complete sentence. Return only the Korean summary without any prefix, explanation, or brackets. Format: one line per sentence."
                        },
                        {
                            "role": "user",
                            "content": summary or title
                        }
                    ],
                    "temperature": 0.3
                },
                timeout=30.0
            )
            
            # HTTP 상태 코드 확인
            summary_response.raise_for_status()
            summary_data = summary_response.json()
            
            # 응답 구조 검증
            if "choices" not in summary_data or not summary_data["choices"]:
                error_msg = summary_data.get("error", {}).get("message", "Unknown error") if "error" in summary_data else "No choices in response"
                raise ValueError(f"LLM API 응답 오류: {error_msg}")
            
            ko_title = title_data["choices"][0]["message"]["content"].strip()
            ko_summary = summary_data["choices"][0]["message"]["content"].strip()
            
            # [번역], [요약] 같은 접두사 제거
            ko_title = ko_title.replace("[번역]", "").strip()
            ko_summary = ko_summary.replace("[요약]", "").replace("[번역]", "").strip()
            
            return ko_title, ko_summary
            
    except httpx.HTTPStatusError as e:
        error_detail = ""
        try:
            error_detail = e.response.json()
        except:
            error_detail = e.response.text[:500]
        print(f"LLM API HTTP error ({e.response.status_code}): {error_detail}")
        # 폴백: 원문을 한글 필드에 저장 (최소한 표시되도록)
        ko_title = title
        ko_summary = summary[:500] if summary else title[:200]
        return ko_title, ko_summary
    except (KeyError, ValueError) as e:
        print(f"LLM API 응답 파싱 오류: {e}")
        # 폴백: 원문을 한글 필드에 저장 (최소한 표시되도록)
        ko_title = title
        ko_summary = summary[:500] if summary else title[:200]
        return ko_title, ko_summary
    except Exception as e:
        print(f"LLM API error: {type(e).__name__}: {e}")
        # 폴백: 원문을 한글 필드에 저장 (최소한 표시되도록)
        ko_title = title
        ko_summary = summary[:500] if summary else title[:200]
        return ko_title, ko_summary


async def translate_to_korean(text: str, context: str = "") -> str:
    """
    텍스트를 한국어로 번역
    context: 번역 컨텍스트 (예: "경제 지표", "기업명", "이벤트명")
    """
    if not text:
        return ""
    
    # 런타임에 최신 API 설정 로드
    current_api_key, current_api_url, current_model = _load_api_config()
    
    if not current_api_key:
        # API 키가 없으면 원문을 그대로 반환 (최소한 표시되도록)
        return text
    
    try:
        async with httpx.AsyncClient() as client:
            system_prompt = f"You are a professional translator. Translate the following English {context} text to natural Korean. Return only the translated text without any prefix, explanation, or brackets."
            if context:
                system_prompt = f"You are a professional translator specializing in financial terminology. Translate the following English {context} to natural Korean. Return only the translated text without any prefix, explanation, or brackets."
            
            # DeepSeek API 헤더 설정
            headers = {
                "Authorization": f"Bearer {current_api_key}",
                "Content-Type": "application/json"
            }
            response = await client.post(
                current_api_url,
                headers=headers,
                json={
                    "model": current_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": text
                        }
                    ],
                    "temperature": 0.3
                },
                timeout=30.0
            )
            
            # HTTP 상태 코드 확인
            response.raise_for_status()
            response_data = response.json()
            
            # 응답 구조 검증
            if "choices" not in response_data or not response_data["choices"]:
                error_msg = response_data.get("error", {}).get("message", "Unknown error") if "error" in response_data else "No choices in response"
                raise ValueError(f"LLM API 응답 오류: {error_msg}")
            
            translated = response_data["choices"][0]["message"]["content"].strip()
            # [번역] 같은 접두사 제거
            translated = translated.replace("[번역]", "").strip()
            return translated
            
    except httpx.HTTPStatusError as e:
        error_detail = ""
        try:
            error_detail = e.response.json()
            error_msg = error_detail.get("error", {}).get("message", "") if isinstance(error_detail, dict) else str(error_detail)
        except:
            error_detail = e.response.text[:500]
            error_msg = error_detail
        
        status_code = e.response.status_code
        print(f"LLM translation HTTP error ({status_code}): {error_msg}")
        
        if status_code == 401:
            print("[LLM_PROVIDER] API 키 인증 실패 (401). LLM_API_KEY 환경 변수를 확인하세요.")
        return text
    except (KeyError, ValueError) as e:
        print(f"LLM translation 응답 파싱 오류: {e}")
        # 폴백: 원문 반환 (최소한 표시되도록)
        return text
    except Exception as e:
        print(f"LLM translation error: {type(e).__name__}: {e}")
        # 폴백: 원문 반환 (최소한 표시되도록)
        return text

async def analyze_sentiment(title: str, summary: str = "") -> str:
    """
    LLM을 사용하여 뉴스의 시장 심리(Sentiment)를 분석
    반환값: 'bullish', 'bearish', 'neutral'
    """
    # 런타임에 최신 API 설정 로드
    current_api_key, current_api_url, current_model = _load_api_config()
    
    if not current_api_key:
        return "neutral"
    
    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {current_api_key}",
                "Content-Type": "application/json"
            }
            response = await client.post(
                current_api_url,
                headers=headers,
                json={
                    "model": current_model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "You are a specialized financial NLP model. Analyze the market sentiment of the following news. Classify it as exactly one of: 'bullish', 'bearish', or 'neutral'. Return only the single word."
                        },
                        {
                            "role": "user",
                            "content": f"Title: {title}\nSummary: {summary}"
                        }
                    ],
                    "temperature": 0.1
                },
                timeout=20.0
            )
            
            # HTTP 상태 코드 확인
            response.raise_for_status()
            response_data = response.json()
            
            # 응답 구조 검증
            if "choices" not in response_data or not response_data["choices"]:
                error_msg = response_data.get("error", {}).get("message", "Unknown error") if "error" in response_data else "No choices in response"
                raise ValueError(f"LLM API 응답 오류: {error_msg}")
            
            sentiment = response_data["choices"][0]["message"]["content"].strip().lower()
            if "bullish" in sentiment: return "bullish"
            if "bearish" in sentiment: return "bearish"
            return "neutral"
            
    except httpx.HTTPStatusError as e:
        error_detail = ""
        try:
            error_detail = e.response.json()
            error_msg = error_detail.get("error", {}).get("message", "") if isinstance(error_detail, dict) else str(error_detail)
        except:
            error_detail = e.response.text[:500]
            error_msg = error_detail
        
        status_code = e.response.status_code
        print(f"Sentiment analysis HTTP error ({status_code}): {error_msg}")
        
        if status_code == 401:
            print("[LLM_PROVIDER] API 키 인증 실패 (401). LLM_API_KEY 환경 변수를 확인하세요.")
        return "neutral"
    except (KeyError, ValueError) as e:
        print(f"Sentiment analysis 응답 파싱 오류: {e}")
        return "neutral"
    except Exception as e:
        print(f"Sentiment analysis error: {type(e).__name__}: {e}")
        return "neutral"


async def briefing_analyst_reply(
    symbol: str,
    user_message: str,
    context: dict,
) -> str:
    """
    실시간 브리핑 애널리스트 페르소나로 LLM 답변 생성.
    context: {"news": [...], "upcoming_events": [...], "recent_releases": [...]}
    각 항목은 최소 title, time (선택 source/importance/value/forecast).
    데이터가 없으면 방어 프롬프트를 넣어 지정학·이벤트를 지어내지 않도록 함.
    """
    from app.prompts.briefing_analyst import BRIEFING_ANALYST_SYSTEM, BRIEFING_ANALYST_DEFENSE_WHEN_NO_DATA

    current_api_key, current_api_url, current_model = _load_api_config()
    if not current_api_key:
        return "현재 브리핑 서비스를 사용할 수 없습니다. (API 설정 확인 필요)"

    news_list = context.get("news") or []
    events_list = context.get("upcoming_events") or []
    releases_list = context.get("recent_releases") or []

    has_any_data = bool(news_list or events_list or releases_list)

    # 컨텍스트를 '리포트 템플릿'처럼 보이지 않게, 짧은 구조화 데이터로 전달
    payload = {
        "symbol": symbol,
        "user_message": user_message,
        "news": news_list[:6],
        "upcoming_events": events_list[:5],
        "recent_releases": releases_list[:5],
    }

    def _no_data_marker() -> str:
        return "현재 제공된 뉴스/일정/지표 데이터가 없습니다."

    user_content = (
        _no_data_marker() if not has_any_data else ""
    ) + "\n" + str(payload)
    system_content = BRIEFING_ANALYST_SYSTEM
    if not has_any_data:
        system_content = system_content + BRIEFING_ANALYST_DEFENSE_WHEN_NO_DATA

    def _normalize_chat_reply(text: str) -> str:
        if not text:
            return ""
        t = text.strip()
        # 과한 마크다운/제목 제거
        for bad in ("##", "#", "**", "__", "`"):
            t = t.replace(bad, "")
        # 번호 매기기/불릿 라인 제거
        lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
        cleaned = []
        for ln in lines:
            # "1. ..." "2) ..." "- ..." "• ..." 같은 시작은 제거
            if ln[:3].isdigit() and (ln[1:2] in (".", ")")):
                ln = ln[2:].strip(" .)-")
            if ln.startswith(("-", "•", "·")):
                ln = ln.lstrip("-•· ").strip()
            if ln:
                cleaned.append(ln)
        t = " ".join(cleaned).strip()
        # 문장 수 제한(2~4문장)
        # 너무 길면 문장 경계(., ?, !, …, \n) 기준으로 자름
        import re
        sents = [s.strip() for s in re.split(r"(?<=[\.\?\!…])\s+", t) if s.strip()]
        if len(sents) >= 4:
            t = " ".join(sents[:4])
        # 길이 제한
        if len(t) > 420:
            t = t[:420].rstrip() + "…"
        return t

    try:
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {current_api_key}",
                "Content-Type": "application/json",
            }
            response = await client.post(
                current_api_url,
                headers=headers,
                json={
                    "model": current_model,
                    "messages": [
                        {"role": "system", "content": system_content},
                        {"role": "user", "content": user_content},
                    ],
                    "temperature": 0.6,
                    "max_tokens": 220,
                },
                timeout=45.0,
            )
            response.raise_for_status()
            data = response.json()
            if "choices" not in data or not data["choices"]:
                return "브리핑 생성 중 일시 오류가 났습니다. 잠시 후 다시 요청해 주세요."
            raw = data["choices"][0]["message"]["content"].strip()
            return _normalize_chat_reply(raw)
    except Exception as e:
        print(f"[BRIEFING_ANALYST] LLM error: {e}")
        return "브리핑 생성 중 일시 오류가 났습니다. 잠시 후 다시 요청해 주세요."