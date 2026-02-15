import math
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.chat import Offer
from app.models.order import Order
from app.models.user import AdvertiserProfile, User
from app.schemas.offer import (
    OfferCancelResponse,
    OfferListItem,
    OfferListResponse,
    OfferOrderBrief,
    OfferParticipant,
    OfferViewResponse,
    PaginationMeta,
)

router = APIRouter(prefix="/offers", tags=["Offers"])


async def _build_participant(db: AsyncSession, user_id) -> OfferParticipant:
    result = await db.execute(select(User).where(User.id == user_id))
    u = result.scalar_one_or_none()
    company_name = None
    if u and u.role == "advertiser":
        adv_result = await db.execute(select(AdvertiserProfile).where(AdvertiserProfile.user_id == u.id))
        adv = adv_result.scalar_one_or_none()
        company_name = adv.company_name if adv else None
    return OfferParticipant(
        id=str(user_id),
        name=u.name if u else None,
        avatar_url=u.avatar_url if u else None,
        company_name=company_name,
    )


async def _build_offer_item(db: AsyncSession, offer: Offer) -> OfferListItem:
    order_result = await db.execute(select(Order).where(Order.id == offer.order_id))
    order = order_result.scalar_one_or_none()

    return OfferListItem(
        id=str(offer.id),
        order=OfferOrderBrief(id=str(offer.order_id), title=order.title if order else ""),
        sender=await _build_participant(db, offer.sender_id),
        recipient=await _build_participant(db, offer.recipient_id),
        budget=offer.budget,
        deadline=str(offer.deadline),
        conditions=offer.conditions,
        start_date=offer.start_date,
        end_date=offer.end_date,
        video_count=offer.video_count,
        content_description=offer.content_description,
        status=offer.status,
        viewed_at=offer.viewed_at,
        created_at=offer.created_at,
    )


@router.get(
    "/my/sent",
    response_model=OfferListResponse,
    summary="Мои отправленные офферы (рекламодатель)",
    description="Список офферов, отправленных текущим рекламодателем. Фильтр по статусу: pending, viewed, accepted, declined, cancelled.",
)
async def my_sent_offers(
    offer_status: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: User = Depends(require_role("advertiser")),
    db: AsyncSession = Depends(get_db),
):
    query = select(Offer).where(Offer.sender_id == user.id)
    if offer_status:
        query = query.where(Offer.status == offer_status)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    total_pages = math.ceil(total / per_page) if total > 0 else 0

    query = query.order_by(Offer.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    offers = result.scalars().all()

    data = [await _build_offer_item(db, o) for o in offers]

    return OfferListResponse(
        data=data,
        meta=PaginationMeta(page=page, per_page=per_page, total=total, total_pages=total_pages),
    )


@router.get(
    "/my/received",
    response_model=OfferListResponse,
    summary="Полученные офферы (креатор)",
    description="Список офферов, полученных текущим креатором. Фильтр по статусу: pending, viewed, accepted, declined, cancelled.",
)
async def my_received_offers(
    offer_status: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: User = Depends(require_role("creator")),
    db: AsyncSession = Depends(get_db),
):
    query = select(Offer).where(Offer.recipient_id == user.id)
    if offer_status:
        query = query.where(Offer.status == offer_status)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    total_pages = math.ceil(total / per_page) if total > 0 else 0

    query = query.order_by(Offer.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    offers = result.scalars().all()

    data = [await _build_offer_item(db, o) for o in offers]

    return OfferListResponse(
        data=data,
        meta=PaginationMeta(page=page, per_page=per_page, total=total, total_pages=total_pages),
    )


@router.post(
    "/{offer_id}/view",
    response_model=OfferViewResponse,
    summary="Отметить оффер просмотренным",
    description="Креатор отмечает оффер как просмотренный. Статус меняется на `viewed` если был `pending`.",
)
async def view_offer(
    offer_id: str,
    user: User = Depends(require_role("creator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Offer).where(Offer.id == offer_id, Offer.recipient_id == user.id))
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Оффер не найден")

    now = datetime.now(timezone.utc)
    if not offer.viewed_at:
        offer.viewed_at = now
    if offer.status == "pending":
        offer.status = "viewed"
    await db.commit()

    return OfferViewResponse(id=str(offer.id), status=offer.status, viewed_at=offer.viewed_at)


@router.post(
    "/{offer_id}/cancel",
    response_model=OfferCancelResponse,
    summary="Отменить оффер (рекламодатель)",
    description="Рекламодатель отменяет свой оффер. Возможно только для статусов `pending` и `viewed`.",
)
async def cancel_offer(
    offer_id: str,
    user: User = Depends(require_role("advertiser")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Offer).where(Offer.id == offer_id, Offer.sender_id == user.id))
    offer = result.scalar_one_or_none()
    if not offer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Оффер не найден")

    if offer.status not in ("pending", "viewed"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя отменить оффер в текущем статусе")

    offer.status = "cancelled"
    offer.cancelled_at = datetime.now(timezone.utc)
    await db.commit()

    return OfferCancelResponse(id=str(offer.id))
