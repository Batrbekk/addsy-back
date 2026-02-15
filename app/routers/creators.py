import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.review import Review
from app.models.user import CreatorProfile, User
from app.schemas.creator import (
    CreatorDetail,
    CreatorListItem,
    CreatorListResponse,
    CreatorSocials,
    PaginationMeta,
)

router = APIRouter(prefix="/creators", tags=["Creators"])


@router.get("", response_model=CreatorListResponse, summary="Список креаторов", description="Поиск и фильтрация креаторов. Фильтры: категория, город, рейтинг. Сортировка: rating, followers, newest.")
async def list_creators(
    q: str | None = None,
    category: str | None = None,
    city: str | None = None,
    min_rating: float | None = None,
    sort: str = "rating",
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(User, CreatorProfile).join(CreatorProfile, CreatorProfile.user_id == User.id).where(User.role == "creator")

    if q:
        query = query.where(User.name.ilike(f"%{q}%"))
    if category:
        query = query.where(CreatorProfile.categories.any(category))
    if city:
        query = query.where(CreatorProfile.city == city)
    if min_rating:
        query = query.where(CreatorProfile.rating >= min_rating)

    # Count
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    total_pages = math.ceil(total / per_page) if total > 0 else 0

    # Sort
    if sort == "followers":
        query = query.order_by(CreatorProfile.followers_count.desc())
    elif sort == "newest":
        query = query.order_by(User.created_at.desc())
    else:
        query = query.order_by(CreatorProfile.rating.desc())

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    rows = result.all()

    data = []
    for user, profile in rows:
        data.append(
            CreatorListItem(
                id=str(user.id),
                name=user.name,
                avatar_url=user.avatar_url,
                bio=profile.bio,
                city=profile.city,
                categories=profile.categories,
                followers_count=profile.followers_count,
                average_reach=profile.average_reach,
                rating=profile.rating,
                reviews_count=profile.reviews_count,
                socials=CreatorSocials(instagram=profile.instagram, tiktok=profile.tiktok),
            )
        )

    return CreatorListResponse(
        data=data,
        meta=PaginationMeta(page=page, per_page=per_page, total=total, total_pages=total_pages),
    )


@router.get("/{creator_id}", response_model=CreatorDetail, summary="Профиль креатора", description="Детальная информация о креаторе: соц. сети, портфолио, разбивка отзывов по рейтингу.")
async def get_creator(
    creator_id: str,
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(User, CreatorProfile)
        .join(CreatorProfile, CreatorProfile.user_id == User.id)
        .where(User.id == creator_id)
    )
    row = result.one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Креатор не найден")

    user, profile = row

    # Review breakdown
    breakdown = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
    review_result = await db.execute(
        select(Review.rating, func.count()).where(Review.reviewee_id == user.id).group_by(Review.rating)
    )
    for rating, count in review_result.all():
        breakdown[str(rating)] = count

    return CreatorDetail(
        id=str(user.id),
        name=user.name,
        avatar_url=user.avatar_url,
        bio=profile.bio,
        city=profile.city,
        country=profile.country,
        categories=profile.categories,
        followers_count=profile.followers_count,
        average_reach=profile.average_reach,
        rating=profile.rating,
        reviews_count=profile.reviews_count,
        socials=CreatorSocials(instagram=profile.instagram, tiktok=profile.tiktok),
        review_breakdown=breakdown,
    )
