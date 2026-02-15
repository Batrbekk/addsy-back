from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.notification import Notification
from app.models.user import User
from app.schemas.notification import (
    MarkAllReadResponse,
    MarkReadResponse,
    NotificationItem,
    NotificationListResponse,
    NotificationMeta,
)

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", response_model=NotificationListResponse, summary="Список уведомлений", description="Уведомления пользователя с пагинацией. Мета включает `unread_count`.")
async def list_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(Notification).where(Notification.user_id == user.id)

    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0
    unread = (
        await db.execute(
            select(func.count())
            .select_from(Notification)
            .where(Notification.user_id == user.id, Notification.is_read == False)
        )
    ).scalar() or 0

    result = await db.execute(
        base.order_by(Notification.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    )
    notifications = result.scalars().all()

    return NotificationListResponse(
        data=[
            NotificationItem(
                id=str(n.id),
                type=n.type,
                title=n.title,
                body=n.body,
                is_read=n.is_read,
                reference_type=n.reference_type,
                reference_id=str(n.reference_id) if n.reference_id else None,
                created_at=n.created_at,
            )
            for n in notifications
        ],
        meta=NotificationMeta(page=page, total=total, unread_count=unread),
    )


@router.post("/{notification_id}/read", response_model=MarkReadResponse, summary="Прочитать уведомление", description="Отмечает уведомление как прочитанное.")
async def mark_read(
    notification_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id)
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Уведомление не найдено")

    notif.is_read = True
    await db.commit()

    return MarkReadResponse(id=str(notif.id))


@router.post("/read-all", response_model=MarkAllReadResponse, summary="Прочитать все", description="Отмечает все непрочитанные уведомления как прочитанные.")
async def mark_all_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read == False)
        .values(is_read=True)
    )
    await db.commit()

    return MarkAllReadResponse(updated_count=result.rowcount)
