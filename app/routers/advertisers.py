import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.review import Review
from app.models.user import AdvertiserProfile, User
from app.schemas.advertiser import (
    AdvertiserDetail,
    AdvertiserListItem,
    AdvertiserListResponse,
    PaginationMeta,
)

router = APIRouter(prefix="/advertisers", tags=["Advertisers"])


@router.get(
    "",
    response_model=AdvertiserListResponse,
    summary="Список рекламодателей",
    description="Поиск и фильтрация рекламодателей. Фильтры: текст (q), отрасль, город, мин. рейтинг. Сортировка: rating, orders, spent, newest.",
)
async def list_advertisers(
    q: str | None = None,
    industry: str | None = None,
    city: str | None = None,
    min_rating: float | None = None,
    sort: str = "rating",
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(User, AdvertiserProfile)
        .join(AdvertiserProfile, AdvertiserProfile.user_id == User.id)
        .where(User.role == "advertiser")
    )

    if q:
        query = query.where(AdvertiserProfile.company_name.ilike(f"%{q}%"))
    if industry:
        query = query.where(AdvertiserProfile.industry == industry)
    if city:
        query = query.where(AdvertiserProfile.city == city)
    if min_rating:
        query = query.where(AdvertiserProfile.rating >= min_rating)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    total_pages = math.ceil(total / per_page) if total > 0 else 0

    if sort == "orders":
        query = query.order_by(AdvertiserProfile.total_orders.desc())
    elif sort == "spent":
        query = query.order_by(AdvertiserProfile.total_spent.desc())
    elif sort == "newest":
        query = query.order_by(User.created_at.desc())
    else:
        query = query.order_by(AdvertiserProfile.rating.desc())

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    rows = result.all()

    data = []
    for user, profile in rows:
        data.append(
            AdvertiserListItem(
                id=str(user.id),
                company_name=profile.company_name,
                logo_url=profile.logo_url,
                industry=profile.industry,
                city=profile.city,
                about=profile.about,
                rating=profile.rating,
                total_orders=profile.total_orders,
                total_spent=profile.total_spent,
            )
        )

    return AdvertiserListResponse(
        data=data,
        meta=PaginationMeta(page=page, per_page=per_page, total=total, total_pages=total_pages),
    )


@router.get(
    "/{advertiser_id}",
    response_model=AdvertiserDetail,
    summary="Профиль рекламодателя",
    description="Детальная информация о рекламодателе: компания, отрасль, рейтинг, разбивка отзывов.",
)
async def get_advertiser(
    advertiser_id: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User, AdvertiserProfile)
        .join(AdvertiserProfile, AdvertiserProfile.user_id == User.id)
        .where(User.id == advertiser_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Рекламодатель не найден")

    user, profile = row

    breakdown = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
    review_result = await db.execute(
        select(Review.rating, func.count()).where(Review.reviewee_id == user.id).group_by(Review.rating)
    )
    for rating, count in review_result.all():
        breakdown[str(rating)] = count

    return AdvertiserDetail(
        id=str(user.id),
        company_name=profile.company_name,
        logo_url=profile.logo_url,
        industry=profile.industry,
        city=profile.city,
        about=profile.about,
        website=profile.website,
        rating=profile.rating,
        total_orders=profile.total_orders,
        total_spent=profile.total_spent,
        review_breakdown=breakdown,
    )
