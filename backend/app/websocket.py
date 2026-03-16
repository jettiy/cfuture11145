from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Message, Channel, User
from app.models import UserRole
from typing import Dict, List
import json
import asyncio

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
            self.active_connections[channel_id].remove(websocket)
    
    async def broadcast_to_channel(self, channel_id: int, message: dict):
        if channel_id in self.active_connections:
            disconnected = []
            for connection in self.active_connections[channel_id]:
                try:
                    await connection.send_json(message)
                except:
                    disconnected.append(connection)
            for conn in disconnected:
                self.disconnect(conn, channel_id)

    async def broadcast_to_all(self, message: dict):
        """모든 채널의 모든 연결에 메시지 전송 (예: 지표 actual 실시간 알림)."""
        disconnected = []
        for channel_id, connections in list(self.active_connections.items()):
            for conn in connections:
                try:
                    await conn.send_json(message)
                except Exception:
                    disconnected.append((channel_id, conn))
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
            db.add(message)
            db.commit()
            db.refresh(message)
            
            # 브로드캐스트
            response = {
                "id": message.id,
                "channel_id": message.channel_id,
                "user_id": user.id,
                "username": user.username,
                "nickname": user.nickname,
                "content": message.content,
                "is_bot": False,
                "user_role": user.role.value,
                "created_at": message.created_at.isoformat()
            }
            await manager.broadcast_to_channel(channel_id, response)

            # @브리핑 호출 시 실시간 브리핑 애널리스트가 답변
            content_stripped = content.strip()
            if content_stripped.startswith("@브리핑") or content_stripped.startswith("브리핑 "):
                symbol = message_data.get("symbol")
                if not symbol:
                    ch = db.query(Channel).filter(Channel.id == channel_id).first()
                    symbol = (ch.symbol if ch else None) or "NQ1!"
                user_question = content_stripped.replace("@브리핑", "").replace("브리핑", "").strip()
                if not user_question:
                    user_question = "선택 종목 기준으로 지금 시장 요약과 체크포인트만 짧게 알려 줘."
                from app.services.ai_chat_service import handle_briefing_analyst
                asyncio.create_task(handle_briefing_analyst(channel_id, symbol, user_question))
            else:
                # @종목명 키워드(주가/실적/뉴스) 형식이면 FMP 데이터 가져와 LLM 답변
                from app.services.chat_command_parser import parse_stock_command
                from app.services.ai_chat_service import handle_stock_command_analyst
                if content_stripped.startswith("@") and parse_stock_command(content_stripped):
                    asyncio.create_task(handle_stock_command_analyst(channel_id, content_stripped))
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel_id)
    finally:
        db.close()
