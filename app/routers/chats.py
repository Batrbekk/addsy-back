from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.chat import Chat, Message, Offer
from app.models.deal import Deal
from app.models.order import Order
from app.models.response import Response
from app.models.user import User
from app.schemas.chat import (
    ChatListItem,
    ChatListResponse,
    CreateChatRequest,
    CreateChatResponse,
    LastMessage,
    MessageItem,
    MessageListResponse,
    OfferBrief,
    OfferMessageResponse,
    ParticipantBrief,
    RespondOfferRequest,
    RespondOfferResponse,
    SendMessageRequest,
    SendOfferRequest,
)

router = APIRouter(prefix="/chats", tags=["Chats"])


def _other_participant_id(chat: Chat, user_id) -> str:
    return str(chat.participant_2) if str(chat.participant_1) == str(user_id) else str(chat.participant_1)


@router.get("", response_model=ChatListResponse, summary="Список чатов", description="Все чаты текущего пользователя с последним сообщением и счётчиком непрочитанных.")
async def list_chats(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chat)
        .where(or_(Chat.participant_1 == user.id, Chat.participant_2 == user.id))
        .order_by(Chat.last_message_at.desc().nullslast())
    )
    chats = result.scalars().all()

    data = []
    for chat in chats:
        other_id = _other_participant_id(chat, user.id)
        other_result = await db.execute(select(User).where(User.id == other_id))
        other = other_result.scalar_one_or_none()

        # Last message
        msg_result = await db.execute(
            select(Message).where(Message.chat_id == chat.id).order_by(Message.created_at.desc()).limit(1)
        )
        last_msg = msg_result.scalar_one_or_none()

        # Unread count
        unread = (
            await db.execute(
                select(func.count())
                .select_from(Message)
                .where(Message.chat_id == chat.id, Message.sender_id != user.id, Message.read_at.is_(None))
            )
        ).scalar() or 0

        data.append(
            ChatListItem(
                id=str(chat.id),
                participant=ParticipantBrief(
                    id=str(other.id) if other else other_id,
                    name=other.name if other else None,
                    avatar_url=other.avatar_url if other else None,
                    role=other.role if other else None,
                ),
                last_message=LastMessage(
                    content=last_msg.content,
                    type=last_msg.type,
                    created_at=last_msg.created_at,
                )
                if last_msg
                else None,
                unread_count=unread,
                order_id=str(chat.order_id) if chat.order_id else None,
                updated_at=chat.last_message_at or chat.created_at,
            )
        )

    return ChatListResponse(data=data)


@router.post("", response_model=CreateChatResponse, status_code=status.HTTP_201_CREATED, summary="Создать чат", description="Создаёт чат между двумя пользователями в контексте заказа. Если чат уже существует — возвращает его.")
async def create_chat(
    body: CreateChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Check if chat already exists between these users for this order
    result = await db.execute(
        select(Chat).where(
            or_(
                and_(Chat.participant_1 == user.id, Chat.participant_2 == body.participant_id),
                and_(Chat.participant_1 == body.participant_id, Chat.participant_2 == user.id),
            ),
            Chat.order_id == body.order_id if body.order_id else True,
        )
    )
    existing = result.scalar_one_or_none()
    if existing:
        other_result = await db.execute(select(User).where(User.id == body.participant_id))
        other = other_result.scalar_one_or_none()
        return CreateChatResponse(
            id=str(existing.id),
            participant=ParticipantBrief(
                id=body.participant_id,
                name=other.name if other else None,
                avatar_url=other.avatar_url if other else None,
                role=other.role if other else None,
            ),
            order_id=str(existing.order_id) if existing.order_id else None,
        )

    chat = Chat(
        participant_1=user.id,
        participant_2=body.participant_id,
        order_id=body.order_id,
    )
    db.add(chat)
    await db.commit()
    await db.refresh(chat)

    other_result = await db.execute(select(User).where(User.id == body.participant_id))
    other = other_result.scalar_one_or_none()

    return CreateChatResponse(
        id=str(chat.id),
        participant=ParticipantBrief(
            id=body.participant_id,
            name=other.name if other else None,
            avatar_url=other.avatar_url if other else None,
            role=other.role if other else None,
        ),
        order_id=str(chat.order_id) if chat.order_id else None,
    )


@router.get("/{chat_id}/messages", response_model=MessageListResponse, summary="Сообщения чата", description="История сообщений чата с курсорной пагинацией. Автоматически отмечает входящие как прочитанные.")
async def get_messages(
    chat_id: str,
    before: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify participant
    result = await db.execute(
        select(Chat).where(
            Chat.id == chat_id,
            or_(Chat.participant_1 == user.id, Chat.participant_2 == user.id),
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Чат не найден")

    query = select(Message).where(Message.chat_id == chat_id)
    if before:
        query = query.where(Message.created_at < before)

    query = query.order_by(Message.created_at.desc()).limit(limit + 1)
    result = await db.execute(query)
    messages = result.scalars().all()

    has_more = len(messages) > limit
    messages = messages[:limit]

    # Mark as read
    for msg in messages:
        if str(msg.sender_id) != str(user.id) and msg.read_at is None:
            msg.read_at = datetime.now(timezone.utc)
    await db.commit()

    return MessageListResponse(
        data=[
            MessageItem(
                id=str(m.id),
                chat_id=str(m.chat_id),
                sender_id=str(m.sender_id),
                type=m.type,
                content=m.content,
                created_at=m.created_at,
                read_at=m.read_at,
            )
            for m in reversed(messages)
        ],
        has_more=has_more,
    )


@router.post("/{chat_id}/messages", response_model=MessageItem, status_code=status.HTTP_201_CREATED, summary="Отправить сообщение", description="Отправка текстового сообщения в чат через REST. Для real-time используйте WebSocket.")
async def send_message(
    chat_id: str,
    body: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chat).where(
            Chat.id == chat_id,
            or_(Chat.participant_1 == user.id, Chat.participant_2 == user.id),
        )
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Чат не найден")

    msg = Message(chat_id=chat.id, sender_id=user.id, type=body.type, content=body.content)
    db.add(msg)
    chat.last_message_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(msg)

    return MessageItem(
        id=str(msg.id),
        chat_id=str(msg.chat_id),
        sender_id=str(msg.sender_id),
        type=msg.type,
        content=msg.content,
        created_at=msg.created_at,
    )


@router.post("/{chat_id}/offer", response_model=OfferMessageResponse, status_code=status.HTTP_201_CREATED, summary="Отправить оффер", description="Рекламодатель отправляет оффер креатору через чат. Указывается бюджет, дедлайн, описание контента.")
async def send_offer(
    chat_id: str,
    body: SendOfferRequest,
    user: User = Depends(require_role("advertiser")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Chat).where(
            Chat.id == chat_id,
            or_(Chat.participant_1 == user.id, Chat.participant_2 == user.id),
        )
    )
    chat = result.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Чат не найден")

    # Get order title
    order_result = await db.execute(select(Order).where(Order.id == body.order_id))
    order = order_result.scalar_one_or_none()

    # Create offer message
    msg = Message(chat_id=chat.id, sender_id=user.id, type="offer", content=f"Оффер: {body.budget} KZT")
    db.add(msg)
    await db.flush()

    recipient_id = _other_participant_id(chat, user.id)

    offer = Offer(
        chat_id=chat.id,
        message_id=msg.id,
        sender_id=user.id,
        recipient_id=recipient_id,
        order_id=body.order_id,
        budget=body.budget,
        deadline=body.deadline,
        content_description=body.content_description,
        conditions=body.conditions,
        start_date=body.start_date,
        end_date=body.end_date,
        video_count=body.video_count,
    )
    db.add(offer)
    chat.last_message_at = datetime.now(timezone.utc)

    # Update response status
    other_id = _other_participant_id(chat, user.id)
    await db.execute(
        select(Response)
        .where(Response.order_id == body.order_id, Response.creator_id == other_id)
    )

    await db.commit()
    await db.refresh(offer)
    await db.refresh(msg)

    return OfferMessageResponse(
        id=str(msg.id),
        chat_id=str(chat.id),
        offer=OfferBrief(
            id=str(offer.id),
            order_title=order.title if order else None,
            budget=offer.budget,
            deadline=str(offer.deadline),
            content_description=offer.content_description,
            conditions=offer.conditions,
            start_date=str(offer.start_date) if offer.start_date else None,
            end_date=str(offer.end_date) if offer.end_date else None,
            video_count=offer.video_count,
            status=offer.status,
        ),
        created_at=msg.created_at,
    )


@router.post("/{chat_id}/offer/{offer_id}/respond", response_model=RespondOfferResponse, summary="Ответить на оффер", description="Креатор принимает (`accept`) или отклоняет (`decline`) оффер. При accept — создаётся сделка (Deal).")
async def respond_to_offer(
    chat_id: str,
    offer_id: str,
    body: RespondOfferRequest,
    user: User = Depends(require_role("creator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Offer).where(Offer.id == offer_id, Offer.chat_id == chat_id))
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Оффер не найден")

    if offer.status != "pending":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Оффер уже обработан")

    deal_id = None

    # Mark as viewed if not yet
    if not offer.viewed_at:
        offer.viewed_at = datetime.now(timezone.utc)

    if body.action == "accept":
        offer.status = "accepted"

        # Get order and chat info
        order_result = await db.execute(select(Order).where(Order.id == offer.order_id))
        order = order_result.scalar_one_or_none()

        chat_result = await db.execute(select(Chat).where(Chat.id == chat_id))
        chat = chat_result.scalar_one_or_none()

        advertiser_id = _other_participant_id(chat, user.id) if chat else None

        deal = Deal(
            order_id=offer.order_id,
            offer_id=offer.id,
            creator_id=user.id,
            advertiser_id=advertiser_id,
            budget=offer.budget,
            deadline=offer.deadline,
            conditions=offer.conditions,
            start_date=offer.start_date,
            end_date=offer.end_date,
            video_count=offer.video_count,
        )
        db.add(deal)
        await db.flush()
        deal_id = str(deal.id)

    elif body.action == "decline":
        offer.status = "declined"
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Допустимые действия: accept, decline")

    await db.commit()

    return RespondOfferResponse(
        offer_id=str(offer.id),
        status=offer.status,
        deal_id=deal_id,
    )
