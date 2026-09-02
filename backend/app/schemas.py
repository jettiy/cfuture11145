from pydantic import BaseModel, EmailStr, ConfigDict
from typing import Optional, List
from datetime import datetime
from app.models import UserRole

# Auth Schemas
class SignupRequest(BaseModel):
    username: str
    password: str
    nickname: str

class ProUpgradeRequest(BaseModel):
    name: str
    phone: str
    email: EmailStr

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"

# User Schemas
class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: Optional[str]
    email: Optional[str]
    username: str
    nickname: str
    role: UserRole
    balance: float
    pro_request_status: str
    created_at: datetime

class UpdateNicknameRequest(BaseModel):
    nickname: str

# Chat Schemas
class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    channel_id: int
    user_id: Optional[int]
    username: Optional[str]
    nickname: Optional[str]
    content: str
    is_bot: bool
    user_role: Optional[UserRole]
    created_at: datetime

class SendMessageRequest(BaseModel):
    channel_id: int
    content: str

class ChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    symbol: Optional[str]

# News Schemas
class NewsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    original_title: str
    ko_title: Optional[str]
    ko_summary: Optional[str]
    original_link: str
    original_summary: Optional[str] = None
    is_breaking: bool
    importance: str
    sentiment: str = "neutral"
    source: Optional[str]
    published_at: Optional[datetime]
    created_at: datetime

# Signal Schemas
class SignalRequest(BaseModel):
    symbol: str
    timeframe: str
    lookahead_n: Optional[int] = 30

class SignalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    symbol: str
    timeframe: str
    direction: str
    probability: float
    entry_price: float
    take_profit: Optional[float]
    stop_loss: Optional[float]
    risk_reward: Optional[float]
    strategy_title: Optional[str]
    rationale: Optional[str]
    lookahead_n: int
    llm_cost: Optional[float] = None  # LLM API 호출 비용 (USD)
    created_at: datetime

# Support Schemas
class SupportChatResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: int
    admin_id: Optional[int]
    status: str
    request_type: str
    created_at: datetime
    user_name: Optional[str] = None
    user_phone: Optional[str] = None
    user_email: Optional[str] = None
    user_nickname: Optional[str] = None

class SupportMessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    support_chat_id: int
    user_id: int
    content: str
    is_admin: bool
    created_at: datetime

class RespondToSupportRequest(BaseModel):
    content: str

class SendSupportMessageRequest(BaseModel):
    content: str

# Admin Schemas
class UserListResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    username: str
    nickname: str
    role: UserRole
    pro_request_status: str
    created_at: Optional[datetime] = None  # SQLite 마이그레이션 등으로 None일 수 있음

class AdminStatsResponse(BaseModel):
    total_users: int
    member_count: int
    pro_count: int
    admin_count: int
    pending_pro_requests: int

class UpdateUserRoleRequest(BaseModel):
    user_id: int
    role: UserRole

# Indicators & Earnings Schemas
class IndicatorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    name: str
    ko_name: Optional[str]
    country: str
    category: str
    value: Optional[float]
    previous_value: Optional[float]
    forecast: Optional[float]
    unit: Optional[str]
    period: Optional[str]
    release_date: Optional[datetime]
    source: Optional[str]
    is_released: bool
    link: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

class EarningsResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    symbol: str
    company_name: Optional[str]
    ko_company_name: Optional[str]
    quarter: Optional[str]
    earnings_date: Optional[datetime]
    eps_actual: Optional[float]
    eps_forecast: Optional[float]
    revenue_actual: Optional[float]
    revenue_forecast: Optional[float]
    is_after_hours: bool
    market_reaction_percent: Optional[float]
    source: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]

# Calendar Schemas
class CalendarResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    event_name: str
    ko_event_name: Optional[str]
    country: str
    category: str
    importance: str
    scheduled_time: datetime
    actual_value: Optional[str]
    forecast_value: Optional[str]
    previous_value: Optional[str]
    source: Optional[str]
    is_released: bool
    link: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]


class IndexDataResponse(BaseModel):
    """주요 지수 스냅샷 (DB 전용 — FMP 직접 호출 없음)"""
    model_config = ConfigDict(from_attributes=True)
    id: int
    symbol: str
    name: Optional[str] = None
    price: Optional[float] = None
    change: Optional[float] = None
    changes_percentage: Optional[float] = None
    previous_close: Optional[float] = None
    updated_at: datetime
    source: Optional[str] = None


class MergedEventResponse(BaseModel):
    """지표/일정 통합 보드용 단일 이벤트 (economic + custom 통합 렌더링)"""
    id: str  # "economic-{id}" | "custom-{id}"
    type: str  # "economic" | "custom"
    scheduled_at: str  # ISO 8601 (UTC)
    title: str
    description: Optional[str] = None
    country: Optional[str] = None
    importance: Optional[str] = None
    actual_value: Optional[str] = None
    forecast_value: Optional[str] = None
    previous_value: Optional[str] = None
    source_url: Optional[str] = None
    target_symbol: Optional[str] = None
