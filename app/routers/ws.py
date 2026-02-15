from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import or_, select

from app.core.database import async_session
from app.core.security import decode_token
from app.models.chat import Chat, Message
from app.models.user import User

router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    """Manages active WebSocket connections per user."""

    def __init__(self):
        # user_id -> list of WebSocket connections
        self.active: dict[str, list[WebSocket]] = {}

    async def connect(self, user_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(user_id, []).append(ws)

    def disconnect(self, user_id: str, ws: WebSocket):
        if user_id in self.active:
            self.active[user_id] = [c for c in self.active[user_id] if c is not ws]
            if not self.active[user_id]:
                del self.active[user_id]

    async def send_to_user(self, user_id: str, data: dict):
        for ws in self.active.get(user_id, []):
            try:
                await ws.send_json(data)
            except Exception:
                pass

    def is_online(self, user_id: str) -> bool:
        return user_id in self.active and len(self.active[user_id]) > 0


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    # Auth via query param: ws://host/v1/ws?token=<jwt>
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4001, reason="Токен не передан")
        return

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await ws.close(code=4001, reason="Неверный токен")
        return

    user_id = payload["sub"]

    # Verify user exists
    async with async_session() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            await ws.close(code=4001, reason="Пользователь не найден")
            return

    await manager.connect(user_id, ws)

    try:
        while True:
            data = await ws.receive_json()
            action = data.get("action")

            if action == "send_message":
                await _handle_send_message(user_id, data)
            elif action == "typing":
                await _handle_typing(user_id, data)
            elif action == "read":
                await _handle_read(user_id, data)
    except WebSocketDisconnect:
        manager.disconnect(user_id, ws)


async def _handle_send_message(sender_id: str, data: dict):
    chat_id = data.get("chat_id")
    content = data.get("content", "")
    msg_type = data.get("type", "text")

    if not chat_id or not content:
        return

    async with async_session() as db:
        # Verify sender is participant
        result = await db.execute(
            select(Chat).where(
                Chat.id == chat_id,
                or_(Chat.participant_1 == sender_id, Chat.participant_2 == sender_id),
            )
        )
        chat = result.scalar_one_or_none()
        if not chat:
            return

        # Save message
        msg = Message(chat_id=chat.id, sender_id=sender_id, type=msg_type, content=content)
        db.add(msg)
        chat.last_message_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(msg)

        # Determine recipient
        recipient_id = (
            str(chat.participant_2) if str(chat.participant_1) == sender_id else str(chat.participant_1)
        )

        message_data = {
            "event": "new_message",
            "data": {
                "id": str(msg.id),
                "chat_id": str(msg.chat_id),
                "sender_id": sender_id,
                "type": msg.type,
                "content": msg.content,
                "created_at": msg.created_at.isoformat(),
            },
        }

        # Send to recipient
        await manager.send_to_user(recipient_id, message_data)
        # Echo back to sender (confirmation)
        await manager.send_to_user(sender_id, message_data)


async def _handle_typing(sender_id: str, data: dict):
    chat_id = data.get("chat_id")
    if not chat_id:
        return

    async with async_session() as db:
        result = await db.execute(
            select(Chat).where(
                Chat.id == chat_id,
                or_(Chat.participant_1 == sender_id, Chat.participant_2 == sender_id),
            )
        )
        chat = result.scalar_one_or_none()
        if not chat:
            return

        recipient_id = (
            str(chat.participant_2) if str(chat.participant_1) == sender_id else str(chat.participant_1)
        )

        await manager.send_to_user(recipient_id, {
            "event": "typing",
            "data": {"chat_id": chat_id, "user_id": sender_id},
        })


async def _handle_read(user_id: str, data: dict):
    chat_id = data.get("chat_id")
    if not chat_id:
        return

    async with async_session() as db:
        result = await db.execute(
            select(Chat).where(
                Chat.id == chat_id,
                or_(Chat.participant_1 == user_id, Chat.participant_2 == user_id),
            )
        )
        chat = result.scalar_one_or_none()
        if not chat:
            return

        # Mark unread messages as read
        unread_result = await db.execute(
            select(Message).where(
                Message.chat_id == chat_id,
                Message.sender_id != user_id,
                Message.read_at.is_(None),
            )
        )
        messages = unread_result.scalars().all()
        now = datetime.now(timezone.utc)
        for msg in messages:
            msg.read_at = now
        await db.commit()

        # Notify sender that messages were read
        recipient_id = (
            str(chat.participant_2) if str(chat.participant_1) == user_id else str(chat.participant_1)
        )
        await manager.send_to_user(recipient_id, {
            "event": "messages_read",
            "data": {"chat_id": chat_id, "read_by": user_id, "read_at": now.isoformat()},
        })
