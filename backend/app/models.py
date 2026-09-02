from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base
import enum

class UserRole(str, enum.Enum):
    MEMBER = "MEMBER"
    PRO = "PRO"
    ADMIN = "ADMIN"

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=True)  # PRO 요청 시 입력
    phone = Column(String(20), unique=True, nullable=True, index=True)  # PRO 요청 시 입력
    email = Column(String(100), unique=True, nullable=True, index=True)  # PRO 요청 시 입력
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nickname = Column(String(50), unique=True, nullable=False, index=True)
    role = Column(SQLEnum(UserRole), default=UserRole.MEMBER, nullable=False)
    balance = Column(Float, default=10.0, nullable=False)  # 사용자 잔액 (기본 10달러)
    pro_request_status = Column(String(20), default="none", nullable=False)  # none, pending, approved, rejected
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    messages = relationship("Message", back_populates="user")
    support_chats = relationship("SupportChat", foreign_keys="SupportChat.user_id", back_populates="user")
    signals = relationship("Signal", back_populates="user")

class Channel(Base):
    __tablename__ = "channels"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, nullable=False)
    symbol = Column(String(20), nullable=True)  # null이면 Global 채널
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    messages = relationship("Message", back_populates="channel")

class Message(Base):
    __tablename__ = "messages"
    
    id = Column(Integer, primary_key=True, index=True)
    channel_id = Column(Integer, ForeignKey("channels.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # null이면 봇 메시지
    content = Column(Text, nullable=False)
    is_bot = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    channel = relationship("Channel", back_populates="messages")
    user = relationship("User", back_populates="messages")

class News(Base):
    __tablename__ = "news"
    
    id = Column(Integer, primary_key=True, index=True)
    original_title = Column(String(500), nullable=False)
    original_summary = Column(Text, nullable=True)
    original_link = Column(String(1000), nullable=False)
    ko_title = Column(String(500), nullable=True)
    ko_summary = Column(Text, nullable=True)
    is_breaking = Column(Boolean, default=False, nullable=False)
    importance = Column(String(20), default="normal", nullable=False)  # normal, high, critical
    sentiment = Column(String(20), default="neutral", nullable=False)  # bullish, bearish, neutral
    source = Column(String(100), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    translated_at = Column(DateTime(timezone=True), nullable=True)

class Signal(Base):
    __tablename__ = "signals"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    symbol = Column(String(20), nullable=False)
    timeframe = Column(String(10), nullable=False)  # 1m, 5m, 15m, 30m, 1h, 1d, 1w, 1M
    direction = Column(String(10), nullable=False)  # LONG, SHORT
    probability = Column(Float, nullable=False)  # 0-100
    entry_price = Column(Float, nullable=False)
    take_profit = Column(Float, nullable=True)
    stop_loss = Column(Float, nullable=True)
    risk_reward = Column(Float, nullable=True)
    strategy_title = Column(String(200), nullable=True)
    rationale = Column(Text, nullable=True)
    lookahead_n = Column(Integer, default=30, nullable=False)
    llm_cost = Column(Float, nullable=True)  # LLM API 호출 비용 (USD)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user = relationship("User", back_populates="signals")

class SupportChat(Base):
    __tablename__ = "support_chats"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(String(20), default="pending", nullable=False)  # pending, active, resolved
    request_type = Column(String(20), default="pro_upgrade", nullable=False)  # pro_upgrade, general
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    user = relationship("User", foreign_keys=[user_id], back_populates="support_chats")
    admin = relationship("User", foreign_keys=[admin_id])
    messages = relationship("SupportMessage", back_populates="support_chat")

class SupportMessage(Base):
    __tablename__ = "support_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    support_chat_id = Column(Integer, ForeignKey("support_chats.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    support_chat = relationship("SupportChat", back_populates="messages")
    user = relationship("User")

class AdminLog(Base):
    __tablename__ = "admin_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    admin_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    action = Column(String(100), nullable=False)  # role_change, user_update, etc.
    target_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    details = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    admin = relationship("User", foreign_keys=[admin_id])
    target_user = relationship("User", foreign_keys=[target_user_id])


class EconomicIndicator(Base):
    """경제 지표 (GDP, 인플레이션, 고용 등)"""
    __tablename__ = "economic_indicators"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)  # 지표명 (예: "US CPI", "US GDP")
    ko_name = Column(String(200), nullable=True)  # 한국어 지표명
    country = Column(String(50), nullable=False, default="US")  # 국가 코드
    category = Column(String(50), nullable=False)  # inflation, gdp, employment, etc.
    value = Column(Float, nullable=True)  # 현재 값
    previous_value = Column(Float, nullable=True)  # 이전 값
    forecast = Column(Float, nullable=True)  # 예측값
    unit = Column(String(20), nullable=True)  # 단위 (%, $, etc.)
    period = Column(String(50), nullable=True)  # 기간 (예: "2024-Q1", "2024-01")
    release_date = Column(DateTime(timezone=True), nullable=True)  # 발표일
    source = Column(String(100), nullable=True)  # 출처
    is_released = Column(Boolean, default=False)  # 발표 완료 여부
    link = Column(String(1000), nullable=True)  # 인베스팅닷컴 등 상세 링크
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class Earnings(Base):
    """기업 실적 발표"""
    __tablename__ = "earnings"
    
    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(20), nullable=False, index=True)  # 주식 심볼 (예: "AAPL", "TSLA")
    company_name = Column(String(200), nullable=True)
    ko_company_name = Column(String(200), nullable=True)  # 한국어 회사명
    quarter = Column(String(20), nullable=True)  # 분기 (예: "2024-Q1")
    earnings_date = Column(DateTime(timezone=True), nullable=True)  # 실적 발표일
    eps_actual = Column(Float, nullable=True)  # 실제 EPS
    eps_forecast = Column(Float, nullable=True)  # 예측 EPS
    revenue_actual = Column(Float, nullable=True)  # 실제 매출
    revenue_forecast = Column(Float, nullable=True)  # 예측 매출
    is_after_hours = Column(Boolean, default=False)  # 장 후 발표 여부
    market_reaction_percent = Column(Float, nullable=True)  # 예측 시장 반응 % (예: 5.5)
    source = Column(String(100), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class EconomicCalendar(Base):
    """경제 캘린더 (중요 이벤트 일정)"""
    __tablename__ = "economic_calendar"
    
    id = Column(Integer, primary_key=True, index=True)
    event_name = Column(String(300), nullable=False)  # 이벤트명 (예: "US Non-Farm Payrolls")
    ko_event_name = Column(String(300), nullable=True)  # 한국어 이벤트명
    country = Column(String(50), nullable=False, default="US")
    category = Column(String(50), nullable=False)  # employment, inflation, gdp, etc.
    importance = Column(String(20), default="medium", nullable=False)  # low, medium, high, critical
    scheduled_time = Column(DateTime(timezone=True), nullable=False, index=True)  # 예정 시간
    actual_value = Column(String(100), nullable=True)  # 실제 발표값
    forecast_value = Column(String(100), nullable=True)  # 예측값
    previous_value = Column(String(100), nullable=True)  # 이전 값
    source = Column(String(100), nullable=True)
    is_released = Column(Boolean, default=False)  # 발표 완료 여부
    link = Column(String(1000), nullable=True)  # 관련 뉴스/기사 링크
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())


class IndexData(Base):
    """주요 지수 스냅샷 (FMP quote 수집 — 저수지 패턴)"""
    __tablename__ = "index_data"

    id = Column(Integer, primary_key=True, index=True)
    symbol = Column(String(30), nullable=False, index=True, unique=True)  # ^GSPC, ^IXIC, ^DJI 등
    name = Column(String(100), nullable=True)
    price = Column(Float, nullable=True)
    change = Column(Float, nullable=True)
    changes_percentage = Column(Float, nullable=True)
    previous_close = Column(Float, nullable=True)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    source = Column(String(50), default="FMP", nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class CustomEvent(Base):
    """관리자 등록 특별 이벤트 (예: 엔비디아 GTC, 애플 WWDC 등)"""
    __tablename__ = "custom_events"
    
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(300), nullable=False)  # 이벤트명
    event_date = Column(DateTime(timezone=True), nullable=False, index=True)  # 이벤트 일시 (UTC)
    description = Column(Text, nullable=True)  # 이벤트 설명
    target_symbol = Column(String(50), nullable=True)  # 관련 심볼 (예: "NVDA", "AAPL", "NQ1!")
    importance = Column(String(20), default="high", nullable=False)  # low, medium, high, critical
    link = Column(String(1000), nullable=True)  # 관련 링크
    is_active = Column(Boolean, default=True, nullable=False)  # 활성화 여부
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)  # 등록한 관리자
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    creator = relationship("User", foreign_keys=[created_by])
