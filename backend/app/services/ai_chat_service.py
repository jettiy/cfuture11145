import random
import asyncio
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Message, User, Channel, UserRole, News, EconomicCalendar, EconomicIndicator
from app.websocket import manager
from app.services.llm_provider import briefing_analyst_reply, stock_command_reply
from typing import List, Optional, Any

# 실시간 브리핑 애널리스트 전용 유저 (채팅에서 @브리핑 호출 시 이 계정으로 답변)
BRIEFING_ANALYST_USERNAME = "briefing_analyst"
BRIEFING_ANALYST_NICKNAME = "실시간 브리핑 애널리스트"

AI_PERSONAS = [
    {
        "username": "macro_student",
        "nickname": "거시경제학도 지훈",
        "role": UserRole.PRO,
        "personality": "경제학과 대학원생. 이론과 현실의 괴리를 고민하며 열심히 공부하는 스타일.",
        "slang_type": "macro_student"
    },
    {
        "username": "chart_intern",
        "nickname": "차트분석 인턴 민수",
        "role": UserRole.PRO,
        "personality": "여의도 증권사 인턴. 차트 패턴에 집착하며 상사의 뷰보다 차트를 믿는 스타일.",
        "slang_type": "chart_intern"
    },
    {
        "username": "value_investor",
        "nickname": "가치투자 동아리 회장",
        "role": UserRole.PRO,
        "personality": "재무제표만 파고드는 진지한 가치투자자. 차트는 소음이라고 생각함.",
        "slang_type": "value_investor"
    },
    {
        "username": "market_observer",
        "nickname": "밤샘하는 시장감시자",
        "role": UserRole.PRO,
        "personality": "24시간 시장만 보고 있는 폐인. 뉴스 속보에 가장 민감함.",
        "slang_type": "market_observer"
    },
    {
        "username": "global_correspondent",
        "nickname": "방구석 특파원",
        "role": UserRole.PRO,
        "personality": "해외 토픽과 가십을 좋아하는 정보통. 영어를 잘하는 척 하며 번역해줌.",
        "slang_type": "global_correspondent"
    }
]

SLANG_PATTERNS = {
    "macro_student": [
        "교수님은 필립스 곡선이 죽었다고 하셨는데, 요즘 데이터 보면 좀비처럼 살아나는 것 같아요. 금리 인하가 정말 정답일까요?",
        "거시경제 교과서랑 지금 시장이랑 너무 딴판이에요. 유동성이 이렇게 풀렸는데 인플레가 잡힌다는 게 신기하지 않나요?",
        "어젯밤에 연준 의사록 읽어봤는데, 행간의 의미가 심상치 않더라고요. '매파적 동결'이라는 말이 딱 맞는 것 같습니다.",
        "환율 변동성을 보면 캐리 트레이드 자금이 움직이는 것 같아요. 이론적으로는 설명이 안 되는 움직임인데...",
        "경기 선행지표가 꺾였는데 주가는 오르니까 헷갈리네요. 역시 시장은 비이성적인가 봅니다."
    ],
    "chart_intern": [
        "팀장님은 매도하라고 하는데, 차트는 골든크로스 직전이거든요? 이거 몰래 매수해야 되나...",
        "여기서 헤드앤숄더 패턴 완성되면 나락 갈 수 있어요. 손절 라인 꼭 지키세요.",
        "거래량 터지면서 양봉 떴으니까 이건 찐반등일 확률이 높아요. 제가 배운 대로는 그렇습니다.",
        "RSI 다이버전스 떴네요. 추세 전환 신호입니다. 지금 들어가면 먹을 자리 많아 보여요.",
        "이동평균선 정배열 구간이라서 눌림목 매수가 정석이죠. 교과서적인 타점입니다."
    ],
    "value_investor": [
        "차트 줄긋기 놀이 그만하시고 재무제표 좀 보세요. 이 회사 영업이익률이 깡패라니깐요?",
        "주가는 결국 내재가치로 수렴하게 되어 있어요. 지금 저평가 구간이니까 줍줍해야죠.",
        "PER이 업종 평균보다 낮은데 성장성은 더 좋아요. 이런 보석 같은 종목을 왜 안 사죠?",
        "부채비율이 좀 높긴 한데, 이자보상배수 보면 충분히 감당 가능해요. 걱정 말고 들고 가세요.",
        "워렌 버핏 형님이 말씀하셨죠. 공포에 사라고. 지금이 딱 그 공포 구간입니다."
    ],
    "market_observer": [
        "새벽에 뜬 속보 보셨어요? 중동 쪽 분위기가 심상치 않던데 유가 튈 것 같습니다.",
        "방금 VIX 지수 튀는 거 봤음? 오늘 장 변동성 역대급일 듯. 안전벨트 매세요.",
        "기관들 수급 들어오는 거 보소. 이거 개미 털기 같은데, 속지 마세요.",
        "지금 선물 시장 미결제약정 늘어나는 거 보니까 큰 거 한 방 올 것 같습니다.",
        "오늘 옵션 만기일이라 막판에 흔들기 심할 거예요. 뇌동매매 금지!"
    ],
    "global_correspondent": [
        "블룸버그 터미널 훔쳐보니 월가 애들은 이미 숏 포지션 정리 중이래요. 우리만 몰랐음?",
        "Axios 보도 떴습니다! 트럼프가 또 한마디 했대요. 달러 인덱스 춤출 듯.",
        "로이터 통신 원문 읽어보니까 한국 기사는 오역이 많네요. 핵심은 금리 인상이 아니라 '유지'입니다.",
        "CNBC 앵커가 방금 멘트 날렸는데, 시장 반응이 뜨뜻미지근하네요. 이미 선반영된 듯?",
        "파이낸셜 타임즈 사설이 꽤 날카롭네요. 유럽 쪽 경기 침체가 생각보다 심각하다는 뷰입니다."
    ]
}

REACTIONS = [
    "흥미로운 관점입니다. 추가로 고려해볼 점이 있을까요?",
    "데이터를 다시 확인해보니 그 부분이 맞는 것 같습니다.",
    "역사적 사례와 비교해보면 유사한 패턴이 보입니다.",
    "이론적으로는 그렇지만, 실제 시장에서는 다를 수 있습니다.",
    "좋은 지적입니다. 그 부분을 더 깊이 분석해볼 필요가 있겠네요.",
    "통계적으로 유의미한 관계가 있는지 검증이 필요할 것 같습니다.",
    "다른 각도에서 접근해보면 또 다른 해석이 가능할 수 있습니다.",
    "실증 데이터와 이론적 배경을 함께 고려해야 할 것 같습니다.",
    "시장의 구조적 변화를 반영하면 그 해석이 달라질 수 있습니다.",
    "리스크 관리 측면에서도 고려해야 할 부분이 있겠습니다.",
    "장기적 관점과 단기적 관점을 구분해서 봐야 할 것 같습니다.",
    "다양한 시나리오를 시뮬레이션해보는 것이 도움이 될 것 같습니다."
]

async def ensure_ai_users(db: Session):
    """AI 유저들이 DB에 존재하는지 확인하고 없으면 생성"""
    from app.auth import get_password_hash
    
    for persona in AI_PERSONAS:
        user = db.query(User).filter(User.username == persona["username"]).first()
        if not user:
            user = User(
                username=persona["username"],
                nickname=persona["nickname"],
                password_hash=get_password_hash("ai_bot_password_not_for_login"),
                role=persona["role"],
                balance=100.0
            )
            db.add(user)
    db.commit()

async def get_market_context(db: Session):
    """최신 지표 및 실적 데이터 가져오기"""
    from app.models import EconomicIndicator, Earnings
    
    indicators = db.query(EconomicIndicator).order_by(EconomicIndicator.release_date.desc()).limit(3).all()
    earnings = db.query(Earnings).order_by(Earnings.earnings_date.desc()).limit(3).all()
    
    return {
        "indicators": indicators,
        "earnings": earnings
    }


def _ensure_briefing_analyst_user(db: Session) -> Optional[User]:
    """브리핑 애널리스트 봇 유저가 있으면 반환, 없으면 생성 후 반환"""
    from app.auth import get_password_hash
    user = db.query(User).filter(User.username == BRIEFING_ANALYST_USERNAME).first()
    if not user:
        user = User(
            username=BRIEFING_ANALYST_USERNAME,
            nickname=BRIEFING_ANALYST_NICKNAME,
            password_hash=get_password_hash("briefing_bot_no_login"),
            role=UserRole.PRO,
            balance=0.0,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


def get_briefing_context(db: Session, symbol: str) -> dict:
    """브리핑 LLM에 넣을 뉴스/예정 이벤트/최근 발표 결과 수집. 데이터 없으면 빈 리스트."""
    now = datetime.now(timezone.utc)
    news_rows = (
        db.query(News)
        .order_by(News.created_at.desc())
        .limit(10)
        .all()
    )
    news = [
        {
            "title": (n.ko_title or n.original_title or "").strip(),
            "created_at": n.created_at.isoformat() if n.created_at else "",
            "source": getattr(n, "source", None) or "",
        }
        for n in news_rows
    ]

    end_events = now + timedelta(hours=48)
    events_rows = (
        db.query(EconomicCalendar)
        .filter(
            EconomicCalendar.scheduled_time >= now,
            EconomicCalendar.scheduled_time <= end_events,
            EconomicCalendar.importance.in_(["high", "critical"]),
        )
        .order_by(EconomicCalendar.scheduled_time.asc())
        .limit(10)
        .all()
    )
    upcoming_events = [
        {
            "title": e.ko_event_name or e.event_name or "",
            "scheduled_time": e.scheduled_time.isoformat() if e.scheduled_time else "",
            "importance": e.importance or "",
        }
        for e in events_rows
    ]

    releases_rows = (
        db.query(EconomicIndicator)
        .filter(EconomicIndicator.is_released == True)
        .order_by(EconomicIndicator.release_date.desc())
        .limit(10)
        .all()
    )
    recent_releases = [
        {
            "title": r.ko_name or r.name or "",
            "release_date": r.release_date.isoformat() if r.release_date else "",
            "value": r.value,
            "forecast": r.forecast,
        }
        for r in releases_rows
    ]

    return {
        "news": news,
        "upcoming_events": upcoming_events,
        "recent_releases": recent_releases,
    }


async def handle_briefing_analyst(
    channel_id: int, symbol: str, user_message: str, reply_websocket: Optional[Any] = None
):
    """@브리핑 호출 시: DB 컨텍스트 + FMP 에이전트 수집 -> LLM 브리핑 생성.
    reply_websocket이 있으면 해당 연결에만 전송(개인화). 없으면 채널 전체 broadcast."""
    db = SessionLocal()
    try:
        analyst = _ensure_briefing_analyst_user(db)
        if not analyst:
            return
        context = get_briefing_context(db, symbol)
        # FMP 에이전트: 해당 종목 Quote, 최신 뉴스, Key Metrics 주입
        try:
            from app.services.fmp_service import (
                get_fmp_quote_for_briefing,
                get_fmp_stock_news_for_briefing,
                get_fmp_key_metrics_for_briefing,
            )
            context["fmp_quote_text"] = await get_fmp_quote_for_briefing(symbol)
            context["fmp_news_text"] = await get_fmp_stock_news_for_briefing(symbol, limit=10)
            context["fmp_key_metrics_text"] = await get_fmp_key_metrics_for_briefing(symbol)
        except Exception as e:
            context.setdefault("fmp_quote_text", "")
            context.setdefault("fmp_news_text", "")
            context.setdefault("fmp_key_metrics_text", "")
            print(f"[BRIEFING] FMP agent fetch skip: {e}")
        # FMP 데이터 한국어 번역 후 컨텍스트에 반영 (한국 트레이더 가독성)
        try:
            from app.services.llm_provider import translate_fmp_blob_to_korean
            for key in ("fmp_quote_text", "fmp_news_text", "fmp_key_metrics_text"):
                if context.get(key):
                    context[key] = await translate_fmp_blob_to_korean(context[key])
        except Exception as e:
            print(f"[BRIEFING] FMP Korean translate skip: {e}")
        # 이벤트/최신 뉴스 성격 질문이면 실시간 웹 검색 병행 (GTC 요약 등)
        try:
            from app.services.web_search_service import get_web_search_for_briefing
            context["web_search_text"] = await get_web_search_for_briefing(user_message, symbol)
        except Exception as e:
            context.setdefault("web_search_text", "")
            print(f"[BRIEFING] Web search skip: {e}")
        reply = await briefing_analyst_reply(symbol=symbol, user_message=user_message, context=context)
        msg = Message(
            channel_id=channel_id,
            user_id=analyst.id,
            content=reply,
            is_bot=True,
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        payload = {
            "id": msg.id,
            "channel_id": msg.channel_id,
            "user_id": analyst.id,
            "username": analyst.username,
            "nickname": analyst.nickname,
            "content": msg.content,
            "is_bot": True,
            "user_role": analyst.role.value,
            "created_at": msg.created_at.isoformat(),
            "is_private": bool(reply_websocket),
        }
        if reply_websocket:
            await manager.send_to_websocket(reply_websocket, payload)
        else:
            await manager.broadcast_to_channel(channel_id, payload)
        print(f"[BRIEFING_ANALYST] {analyst.nickname} replied in channel {channel_id} (private={bool(reply_websocket)})")
    except Exception as e:
        print(f"[BRIEFING_ANALYST] Error: {e}")
    finally:
        db.close()


async def handle_stock_command_analyst(
    channel_id: int, content: str, reply_websocket: Optional[Any] = None
):
    """
    채팅에서 @종목명 키워드(주가/실적/뉴스) 감지 시: 종목명→티커 해석 후 FMP 데이터 조회해 LLM에 주입해 답변.
    reply_websocket이 있으면 해당 연결에만 전송(개인화).
    - 주가/가격/얼마 -> FMP Quote
    - 실적/어닝/매출 -> FMP Earnings(Income Statement + Earnings Surprises)
    - 뉴스/소식 -> FMP Stock News
    """
    from app.services.chat_command_parser import parse_stock_command, resolve_ticker_from_map
    from app.services.fmp_service import (
        get_fmp_quote_for_briefing,
        get_fmp_stock_news_for_briefing,
        get_fmp_earnings_for_briefing,
        get_fmp_ticker_by_name,
    )

    parsed = parse_stock_command(content)
    if not parsed:
        return
    name_norm = parsed.get("name_normalized") or parsed.get("name") or ""
    ticker = resolve_ticker_from_map(name_norm)
    if not ticker:
        ticker = await get_fmp_ticker_by_name(parsed.get("name") or name_norm)
    if not ticker:
        return  # 티커를 찾지 못하면 무시 (또는 "종목을 찾지 못했어요" 메시지 가능)

    cmd = parsed.get("command_type") or "quote"
    if cmd == "quote":
        fmp_text = await get_fmp_quote_for_briefing(ticker)
    elif cmd == "earnings":
        fmp_text = await get_fmp_earnings_for_briefing(ticker)
    elif cmd == "news":
        fmp_text = await get_fmp_stock_news_for_briefing(ticker, limit=8)
    else:
        fmp_text = await get_fmp_quote_for_briefing(ticker)

    if not (fmp_text or "").strip():
        fmp_text = "[FMP 데이터 없음] 해당 종목/기간 데이터를 불러오지 못했습니다."
    else:
        try:
            from app.services.llm_provider import translate_fmp_blob_to_korean
            fmp_text = await translate_fmp_blob_to_korean(fmp_text)
        except Exception:
            pass

    reply = await stock_command_reply(
        symbol=ticker,
        command_type=cmd,
        fmp_data_text=fmp_text,
        user_question=parsed.get("user_question") or "",
    )

    db = SessionLocal()
    try:
        analyst = _ensure_briefing_analyst_user(db)
        if not analyst:
            return
        msg = Message(
            channel_id=channel_id,
            user_id=analyst.id,
            content=reply,
            is_bot=True,
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        payload = {
            "id": msg.id,
            "channel_id": msg.channel_id,
            "user_id": analyst.id,
            "username": analyst.username,
            "nickname": analyst.nickname,
            "content": msg.content,
            "is_bot": True,
            "user_role": analyst.role.value,
            "created_at": msg.created_at.isoformat(),
            "is_private": bool(reply_websocket),
        }
        if reply_websocket:
            await manager.send_to_websocket(reply_websocket, payload)
        else:
            await manager.broadcast_to_channel(channel_id, payload)
        print(f"[STOCK_COMMAND] {analyst.nickname} replied in channel {channel_id} (ticker={ticker}, type={cmd}, private={bool(reply_websocket)})")
    except Exception as e:
        print(f"[STOCK_COMMAND] Error: {e}")
    finally:
        db.close()


async def trigger_random_ai_chat():
    """랜덤하게 AI 페르소나가 채팅을 남기게 함 (통합 브로드캐스트)"""
    db = SessionLocal()
    try:
        await ensure_ai_users(db)
        
        persona_data = random.choice(AI_PERSONAS)
        persona_user = db.query(User).filter(User.username == persona_data["username"]).first()
        
        if not persona_user: return

        channel_id = 1
        context = await get_market_context(db)
        content = ""
        rand = random.random()

        if rand < 0.3:
            if context["indicators"] and random.random() < 0.6:
                ind = random.choice(context["indicators"])
                if persona_data["slang_type"] == "macro_student": # 거시경제학도
                    content = f"{ind.ko_name or ind.name} 지표가 {ind.value}{ind.unit or ''}로 발표됐네요. 교수님 말씀대로면 이게 통화정책에 영향을 줄 텐데, 교과서랑 현실이랑 너무 달라요..."
                elif persona_data["slang_type"] == "chart_intern": # 차트인턴
                    content = f"{ind.ko_name or ind.name} 떴다! 팀장님은 이거 악재라고 하는데, 차트상으로는 선반영된 거 아닌가요? 지금이 찐바닥 같은데."
                elif persona_data["slang_type"] == "value_investor": # 가치투자자
                    content = f"{ind.ko_name or ind.name} 결과가 어떻든 기업의 내재가치는 변하지 않습니다. 오히려 공포에 매수할 기회죠."
                else:
                    content = f"{ind.ko_name or ind.name} 지표 발표됐습니다. 시장 변동성 확대 주의하세요."
            
            if not content and context["earnings"] and random.random() < 0.5:
                earn = random.choice(context["earnings"])
                if persona_data["slang_type"] == "value_investor":
                    content = f"{earn.symbol} 실적 나왔네요. 영업이익률이 핵심입니다. 단기 주가보다는 펀더멘털을 봐야죠."
                elif persona_data["slang_type"] == "chart_intern":
                    content = f"{earn.symbol} 실적 발표 직후 거래량 터지는 거 보세요. 이거 세력들 장난질 같은데?"
                else:
                    content = f"{earn.symbol} 실적 발표했습니다. 시장 반응 체크해보세요."

        if not content and rand < 0.5:
            content = random.choice(REACTIONS)

        if not content:
            pool = SLANG_PATTERNS.get(persona_data["slang_type"], SLANG_PATTERNS["macro_student"])
            content = random.choice(pool)

        if not content: 
            content = "시장을 분석하는 데 있어 다양한 관점을 고려하는 것이 중요합니다."

        message = Message(channel_id=channel_id, user_id=persona_user.id, content=content, is_bot=False)
        db.add(message)
        db.commit()
        db.refresh(message)

        response = {
            "id": message.id, "channel_id": message.channel_id,
            "user_id": persona_user.id, "username": persona_user.username,
            "nickname": persona_user.nickname, "content": message.content,
            "is_bot": False, "user_role": persona_user.role.value,
            "created_at": message.created_at.isoformat()
        }
        await manager.broadcast_to_channel(channel_id, response)
        print(f"[AI_CHAT] {persona_user.nickname}: {content}")

    except Exception as e: print(f"[AI_CHAT] Error: {e}")
    finally: db.close()

async def handle_ai_response(channel_id: int, user_message: str, user_nickname: str):
    """유저 메시지에 대한 AI 페르소나의 응답 처리 (백엔드 통합)"""
    db = SessionLocal()
    try:
        await ensure_ai_users(db)
        
        mentioned_persona = None
        for persona in AI_PERSONAS:
            if persona["nickname"] in user_message or persona["username"] in user_message:
                mentioned_persona = persona
                break
        
        is_indicator_query = any(word in user_message for word in ["지표", "발표", "결과", "데이터"])
        
        if mentioned_persona or is_indicator_query or random.random() < 0.05:
            persona_data = mentioned_persona or random.choice(AI_PERSONAS)
            persona_user = db.query(User).filter(User.username == persona_data["username"]).first()
            if not persona_user: return

            await asyncio.sleep(random.uniform(2, 4))
            
            context = await get_market_context(db)
            content = ""
            msg_lower = user_message.lower()

            if is_indicator_query and context["indicators"]:
                ind = context["indicators"][0]
                if persona_data["slang_type"] == "macro_student":
                    content = f"{ind.ko_name or ind.name} 지표가 {ind.value}{ind.unit or ''}입니다. 이론적으로 이게 금리에 영향을 줘야 하는데, 시장은 반대로 가네요? 헷갈립니다."
                elif persona_data["slang_type"] == "chart_intern":
                    content = f"{ind.ko_name or ind.name} 결과 상관없어요. 차트는 이미 선반영하고 있습니다. 지금 양봉 뜨는 거 안 보이세요?"
                else:
                    content = f"{ind.ko_name or ind.name} 지표 확인했습니다. 시장 흐름을 잘 살피세요."

            elif any(word in msg_lower for word in ["경기", "침체", "리세션"]):
                if persona_data["slang_type"] == "macro_student":
                    content = "경기 침체요? 교수님은 아직 아니라고 하시는데, 지표들은 좀 불안하네요. 스태그플레이션 오면 답도 없는데."
                elif persona_data["slang_type"] == "value_investor":
                    content = "경기 침체는 오히려 저가 매수의 기회입니다. 우량주들이 바겐세일 중인데 왜 겁을 먹죠?"

            elif any(word in msg_lower for word in ["금리", "통화정책", "연준"]):
                if persona_data["slang_type"] == "macro_student":
                    content = "연준 파월 의장님 발언 들으셨어요? 매파적인 척하면서 비둘기 날리는 거, 완전 고단수라니까요."
                elif persona_data["slang_type"] == "chart_intern":
                    content = "금리고 뭐고 나스닥 차트가 20일선 지지받았습니다. 이게 팩트에요."

            elif any(word in msg_lower for word in ["차트", "기술적", "RSI", "MACD"]):
                if persona_data["slang_type"] == "chart_intern":
                    content = "오! 차트 좀 보시나 봐요? RSI 다이버전스랑 거래량 터지는 거 같이 보면 승률 떡상합니다."
                elif persona_data["slang_type"] == "value_investor":
                    content = "차트는 후행성 지표일 뿐입니다. 기업의 본질적 가치에 집중하세요."

            if not content: 
                content = random.choice(REACTIONS)

            message = Message(channel_id=channel_id, user_id=persona_user.id, content=content, is_bot=False)
            db.add(message)
            db.commit()
            db.refresh(message)

            response = {
                "id": message.id, "channel_id": message.channel_id,
                "user_id": persona_user.id, "username": persona_user.username,
                "nickname": persona_user.nickname, "content": message.content,
                "is_bot": False, "user_role": persona_user.role.value,
                "created_at": message.created_at.isoformat()
            }
            await manager.broadcast_to_channel(channel_id, response)

            # 다른 AI가 끼어들 확률 (15%)
            if random.random() < 0.15:
                await asyncio.sleep(random.uniform(2, 4))
                other_personas = [p for p in AI_PERSONAS if p["nickname"] != persona_data["nickname"]]
                second_persona = random.choice(other_personas)
                # 재귀 호출 대신 직접 처리하거나 간단하게 리액션
                # 여기서는 간단하게 리액션 처리
                pass

    except Exception as e: print(f"[AI_RESPONSE] Error: {e}")
    finally: db.close()
