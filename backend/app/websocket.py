from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Message, Channel, User
from app.models import UserRole
from typing import Dict, List, Optional
import json
import asyncio
import logging
import time
from datetime import datetime, timezone
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)

# 이미지 메시지: content가 data:image 로 시작하면 이미지. Pro/Admin만 허용.
def _is_image_content(content: str) -> bool:
    if not content or len(content) < 50:
        return False
    return content.strip().startswith("data:image") or content.strip().startswith("[IMAGE]:")

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[int, List[WebSocket]] = {}  # channel_id -> [websockets]
    
    async def connect(self, websocket: WebSocket, channel_id: int):
        await websocket.accept()
        if channel_id not in self.active_connections:
            self.active_connections[channel_id] = []
        self.active_connections[channel_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, channel_id: int):
        if channel_id in self.active_connections:
            try:
                self.active_connections[channel_id].remove(websocket)
            except ValueError:
                pass
    
    async def send_to_websocket(self, websocket: WebSocket, message: dict) -> bool:
        """단일 연결에만 전송. 실패 시 False, 한 연결 끊김으로 다른 유저에 영향 없음."""
        try:
            await websocket.send_json(message)
            return True
        except Exception as e:
            logger.debug("[WS] send_to_websocket failed: %s", e)
            return False
    
    async def broadcast_to_channel(self, channel_id: int, message: dict):
        """채널 내 모든 연결에 전송. 한 명 끊겨도 나머지에는 정상 전달되도록 예외 처리."""
        if channel_id not in self.active_connections:
            return
        disconnected = []
        for connection in list(self.active_connections[channel_id]):
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.debug("[WS] broadcast_to_channel send failed: %s", e)
                disconnected.append(connection)
        for conn in disconnected:
            self.disconnect(conn, channel_id)

    async def broadcast_to_all(self, message: dict):
        """모든 채널의 모든 연결에 메시지 전송 (예: 지표 actual 실시간 알림)."""
        disconnected = []
        for cid, connections in list(self.active_connections.items()):
            for conn in list(connections):
                try:
                    await conn.send_json(message)
                except Exception as e:
                    logger.debug("[WS] broadcast_to_all send failed: %s", e)
                    disconnected.append((cid, conn))
        for cid, conn in disconnected:
            self.disconnect(conn, cid)

manager = ConnectionManager()

async def get_current_user_ws(token: str, db: Session):
    from jose import jwt, JWTError
    from app.auth import SECRET_KEY, ALGORITHM
    
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            return None
        user = db.query(User).filter(User.username == username).first()
        return user
    except JWTError:
        return None

@router.websocket("/chat/{channel_id}")
async def websocket_endpoint(websocket: WebSocket, channel_id: int, token: str = None):
    db = SessionLocal()
    user = None
    
    if token:
        user = await get_current_user_ws(token, db)
    
    await manager.connect(websocket, channel_id)
    
    try:
        while True:
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if not user:
                await websocket.send_json({"error": "Authentication required"})
                continue

            content = message_data.get("content", "").strip()
            # 이미지 업로드: Pro/Admin만 허용
            if _is_image_content(content):
                if user.role not in (UserRole.PRO, UserRole.ADMIN):
                    await websocket.send_json({"error": "이미지 업로드는 PRO 또는 관리자만 가능합니다."})
                    continue

            # 메시지 저장
            message = Message(
                channel_id=channel_id,
                user_id=user.id,
                content=content,
                is_bot=False
            )
            persisted = False
            try:
                db.add(message)
                db.commit()
                db.refresh(message)
                persisted = True
            except SQLAlchemyError as e:
                # DB 저장 실패(예: FK/channel 없음)라도 WS 루프가 죽지 않게 보호
                db.rollback()
                logger.exception("[WS] DB write failed (will still broadcast/echo): %s", e)
            
            response = {
                # 저장 실패 시에도 프론트 중복 방지/렌더링을 위해 임시 id 제공
                "id": message.id if persisted else int(time.time() * 1000),
                "channel_id": channel_id,
                "user_id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "content": content,
                "is_bot": False,
                "user_role": user.role.value,
                "created_at": (message.created_at.isoformat() if persisted and message.created_at else datetime.now(timezone.utc).isoformat()),
                "is_private": False,
            }
            content_stripped = content.strip()
            is_ai_call = content_stripped.startswith("@")
            
            if is_ai_call:
                # AI 호출: broadcast 하지 않고, 해당 유저에게만 Echo. AI 답변도 해당 websocket으로만 전송.
                await manager.send_to_websocket(websocket, response)
                if content_stripped.startswith("@브리핑") or content_stripped.startswith("브리핑 "):
                    symbol = message_data.get("symbol")
                    if not symbol:
                        ch = db.query(Channel).filter(Channel.id == channel_id).first()
                        symbol = (ch.symbol if ch else None) or "NQ1!"
                    user_question = content_stripped.replace("@브리핑", "").replace("브리핑", "").strip()
                    if not user_question:
                        user_question = "선택 종목 기준으로 지금 시장 요약과 체크포인트만 짧게 알려 줘."
                    from app.services.ai_chat_service import handle_briefing_analyst
                    asyncio.create_task(handle_briefing_analyst(channel_id, symbol, user_question, reply_websocket=websocket))
                else:
                    from app.services.chat_command_parser import parse_stock_command
                    from app.services.ai_chat_service import handle_stock_command_analyst
                    if parse_stock_command(content_stripped):
                        asyncio.create_task(handle_stock_command_analyst(channel_id, content_stripped, reply_websocket=websocket))
            else:
                # 일반 채팅: 전체 브로드캐스트
                await manager.broadcast_to_channel(channel_id, response)
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel_id)
    finally:
        db.close()
