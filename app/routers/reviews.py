from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.deal import Deal
from app.models.review import Review
from app.models.user import User
from app.schemas.review import (
    CreateReviewRequest,
    CreateReviewResponse,
    ReviewItem,
    ReviewListResponse,
    ReviewMeta,
    ReviewSummary,
    ReviewerBrief,
)

router = APIRouter(prefix="/reviews", tags=["Reviews"])


@router.get("/{user_id}", response_model=ReviewListResponse, summary="Отзывы пользователя", description="Список отзывов о пользователе с рейтинговой сводкой (average, breakdown по 1-5).")
async def get_reviews(
    user_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    base = select(Review).where(Review.reviewee_id == user_id)
    total = (await db.execute(select(func.count()).select_from(base.subquery()))).scalar() or 0

    # Average
    avg = (
        await db.execute(select(func.avg(Review.rating)).where(Review.reviewee_id == user_id))
    ).scalar() or 0.0

    # Breakdown
    breakdown_result = await db.execute(
        select(Review.rating, func.count()).where(Review.reviewee_id == user_id).group_by(Review.rating)
    )
    breakdown = {"5": 0, "4": 0, "3": 0, "2": 0, "1": 0}
    for rating, count in breakdown_result.all():
        breakdown[str(rating)] = count

    # Reviews
    result = await db.execute(
        base.order_by(Review.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    )
    reviews = result.scalars().all()

    data = []
    for r in reviews:
        reviewer_result = await db.execute(select(User).where(User.id == r.reviewer_id))
        reviewer = reviewer_result.scalar_one_or_none()
        data.append(
            ReviewItem(
                id=str(r.id),
                reviewer=ReviewerBrief(
                    id=str(r.reviewer_id),
                    name=reviewer.name if reviewer else None,
                    avatar_url=reviewer.avatar_url if reviewer else None,
                    role=reviewer.role if reviewer else None,
                ),
                rating=r.rating,
                text=r.text,
                order_title=r.order_title,
                deal_id=str(r.deal_id),
                created_at=r.created_at,
            )
        )

    return ReviewListResponse(
        summary=ReviewSummary(average_rating=round(float(avg), 1), total_count=total, breakdown=breakdown),
        data=data,
        meta=ReviewMeta(page=page, total=total),
    )


@router.post("", response_model=CreateReviewResponse, status_code=status.HTTP_201_CREATED, summary="Оставить отзыв", description="Отзыв по завершённой сделке. Рейтинг 1-5. Один отзыв на сделку от каждой стороны.")
async def create_review(
    body: CreateReviewRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify deal is completed/paid
    result = await db.execute(select(Deal).where(Deal.id == body.deal_id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сделка не найдена")

    if deal.status not in ("completed", "paid"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Отзыв можно оставить только после завершения сделки")

    # Check user is part of the deal
    if str(user.id) != str(deal.creator_id) and str(user.id) != str(deal.advertiser_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Вы не участник этой сделки")

    # Check duplicate
    existing = await db.execute(
        select(Review).where(Review.deal_id == body.deal_id, Review.reviewer_id == user.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Вы уже оставили отзыв по этой сделке")

    # Get order title
    from app.models.order import Order
    order_result = await db.execute(select(Order).where(Order.id == deal.order_id))
    order = order_result.scalar_one_or_none()

    review = Review(
        deal_id=deal.id,
        reviewer_id=user.id,
        reviewee_id=body.user_id,
        rating=body.rating,
        text=body.text,
        order_title=order.title if order else None,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)

    return CreateReviewResponse(
        id=str(review.id),
        rating=review.rating,
        text=review.text,
        created_at=review.created_at,
    )
