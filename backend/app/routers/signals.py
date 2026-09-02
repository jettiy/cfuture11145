from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Signal, User, UserRole
from app.schemas import SignalRequest, SignalResponse
from app.auth import get_current_active_user
from app.services.signal_analysis_service import analyze_signal_with_llm
from typing import List

router = APIRouter()

# 타임프레임: "1", "5", "15", "30", "1H", "1D", "1W", "1M"
# 멤버(MEMBER): 15m 이상만 허용. Pro/Admin: 1m, 5m 포함 전체 허용. (백엔드 강제, 우회 호출 차단)
PRO_ONLY_TIMEFRAMES = ["1", "5"]
ALLOWED_TIMEFRAMES = ["1", "5", "15", "30", "1H", "1D", "1W", "1M"]


def require_timeframe_by_role(timeframe: str, user: User) -> None:
    """users.role 기반 타임프레임 허용. 멤버는 15m 이상만, PRO/ADMIN은 1m·5m 포함."""
    if timeframe not in ALLOWED_TIMEFRAMES:
        raise HTTPException(status_code=400, detail=f"Invalid timeframe: {timeframe}")
    if timeframe in PRO_ONLY_TIMEFRAMES and user.role not in (UserRole.PRO, UserRole.ADMIN):
        raise HTTPException(
            status_code=403,
            detail="1m/5m timeframe requires PRO or Admin. Members can use 15m and above."
        )


@router.post("/calculate", response_model=SignalResponse)
async def calculate_signal(
    request: SignalRequest,
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    시그널 = 규칙 엔진(모멘텀/추세/ATR)으로 결정, 이유 = LLM 문장화만.
    멤버는 15m 이상만 허용, PRO/Admin은 1m·5m 포함. (백엔드 강제)
    """
    print(f"[SIGNALS] Calculate request received: user={current_user.username}, symbol={request.symbol}, timeframe={request.timeframe}")
    require_timeframe_by_role(request.timeframe, current_user)
    try:
        # 규칙 엔진 + LLM 문장화
        lookahead_n = request.lookahead_n or 30
        print(f"[SIGNALS_ROUTER] 시그널 분석 요청: symbol={request.symbol}, timeframe={request.timeframe}")
        analysis_result = await analyze_signal_with_llm(
            symbol=request.symbol,
            timeframe=request.timeframe,
            lookahead_n=lookahead_n,
            db=db
        )
        
        # LLM 비용 계산 (로깅용, 실제 차감하지 않음)
        # 실제 비용은 DeepSeek API 계정에서 차감되므로 앱 내부 잔액 체크 제거
        cost = analysis_result.get("llm_cost", 0)
        
        # 시그널 데이터베이스에 저장
        signal = Signal(
            user_id=current_user.id,
            symbol=request.symbol,
            timeframe=request.timeframe,
            direction=analysis_result["direction"],
            probability=analysis_result["probability"],
            entry_price=analysis_result["entry_price"],
            take_profit=analysis_result["take_profit"],
            stop_loss=analysis_result["stop_loss"],
            risk_reward=analysis_result["risk_reward"],
            strategy_title=analysis_result["strategy_title"],
            rationale=analysis_result["rationale"],
            lookahead_n=lookahead_n,
            llm_cost=cost
        )
        db.add(signal)
        
        # 사용자 잔액은 차감하지 않음 (실제 비용은 DeepSeek API 계정에서 차감됨)
        # current_user.balance -= cost  # 주석 처리: DeepSeek API 계정 잔액 사용
        
        db.commit()
        db.refresh(signal)
        
        print(f"[SIGNALS] Signal created for user {current_user.id}: {signal.direction} "
              f"({signal.probability}%) - Cost: ${cost:.6f} - Remaining Balance: ${current_user.balance:.4f}")
        
        return SignalResponse.model_validate(signal)
    except HTTPException:
        raise
    except ValueError as e:
        error_msg = str(e)
        # LLM API 관련 에러인지 확인
        if "인증 실패" in error_msg or "401" in error_msg or ("DeepSeek API" in error_msg and "인증" in error_msg):
            # API 키 인증 실패는 401로 처리
            raise HTTPException(
                status_code=401,
                detail=error_msg
            )
        elif "DeepSeek API" in error_msg or "LLM API" in error_msg or "API 호출 실패" in error_msg:
            # LLM API 호출 실패는 503 (Service Unavailable)로 처리
            raise HTTPException(
                status_code=503,
                detail=error_msg
            )
        # 기타 데이터 부족 등의 오류는 400
        raise HTTPException(
            status_code=400,
            detail=error_msg
        )
    except Exception as e:
        import traceback
        error_msg = str(e)
        print(f"Error in calculate_signal: {error_msg}")
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Signal calculation error: {error_msg}"
        )

@router.get("/my-signals", response_model=List[SignalResponse])
async def get_my_signals(
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
    limit: int = 20
):
    signals = db.query(Signal).filter(
        Signal.user_id == current_user.id
    ).order_by(Signal.created_at.desc()).limit(limit).all()
    return [SignalResponse.model_validate(s) for s in signals]
