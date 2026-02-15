import math

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.order import Order
from app.models.response import Response
from app.models.user import AdvertiserProfile, User
from app.schemas.order import (
    AdvertiserBrief,
    MyOrderItem,
    MyOrderListResponse,
    OrderCreateRequest,
    OrderCreateResponse,
    OrderDetail,
    OrderListItem,
    OrderListResponse,
    PaginationMeta,
)

router = APIRouter(prefix="/orders", tags=["Orders"])


async def _build_advertiser_brief(db: AsyncSession, advertiser_id) -> AdvertiserBrief:
    result = await db.execute(select(AdvertiserProfile).where(AdvertiserProfile.user_id == advertiser_id))
    profile = result.scalar_one_or_none()
    return AdvertiserBrief(
        id=str(advertiser_id),
        company_name=profile.company_name if profile else None,
        logo_url=profile.logo_url if profile else None,
        rating=profile.rating if profile else None,
    )


@router.get("", response_model=OrderListResponse, summary="Лента заказов", description="Список активных заказов для креаторов. Фильтры: текст (q), категория, платформа, бюджет, город. Сортировка: newest, budget_high, budget_low, deadline.")
async def list_orders(
    q: str | None = None,
    category: str | None = None,
    platform: str | None = None,
    min_budget: int | None = None,
    max_budget: int | None = None,
    city: str | None = None,
    sort: str = "newest",
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Order).where(Order.status == "active")

    if q:
        query = query.where(Order.title.ilike(f"%{q}%") | Order.description.ilike(f"%{q}%"))
    if category:
        query = query.where(Order.categories.any(category))
    if platform:
        query = query.where(Order.platform == platform)
    if min_budget:
        query = query.where(Order.budget >= min_budget)
    if max_budget:
        query = query.where(Order.budget <= max_budget)
    if city:
        query = query.where(Order.city == city)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    total_pages = math.ceil(total / per_page) if total > 0 else 0

    if sort == "budget_high":
        query = query.order_by(Order.budget.desc())
    elif sort == "budget_low":
        query = query.order_by(Order.budget.asc())
    elif sort == "deadline":
        query = query.order_by(Order.deadline.asc())
    else:
        query = query.order_by(Order.created_at.desc())

    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    orders = result.scalars().all()

    data = []
    for order in orders:
        adv = await _build_advertiser_brief(db, order.advertiser_id)
        data.append(
            OrderListItem(
                id=str(order.id),
                advertiser=adv,
                title=order.title,
                description=order.description,
                budget=order.budget,
                currency=order.currency,
                deadline=order.deadline,
                platform=order.platform,
                content_type=order.content_type,
                content_count=order.content_count,
                content_duration_min=order.content_duration_min,
                content_duration_max=order.content_duration_max,
                categories=order.categories,
                city=order.city,
                status=order.status,
                response_count=order.response_count,
                created_at=order.created_at,
            )
        )

    return OrderListResponse(
        data=data,
        meta=PaginationMeta(page=page, per_page=per_page, total=total, total_pages=total_pages),
    )


@router.get("/my", response_model=MyOrderListResponse, summary="Мои заказы (рекламодатель)", description="Список заказов текущего рекламодателя. Фильтр по статусу: active, in_progress, completed.")
async def my_orders(
    order_status: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    user: User = Depends(require_role("advertiser")),
    db: AsyncSession = Depends(get_db),
):
    query = select(Order).where(Order.advertiser_id == user.id)
    if order_status:
        query = query.where(Order.status == order_status)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar() or 0
    total_pages = math.ceil(total / per_page) if total > 0 else 0

    query = query.order_by(Order.created_at.desc()).offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    orders = result.scalars().all()

    data = [
        MyOrderItem(
            id=str(o.id),
            title=o.title,
            budget=o.budget,
            currency=o.currency,
            status=o.status,
            response_count=o.response_count,
            created_at=o.created_at,
        )
        for o in orders
    ]

    return MyOrderListResponse(
        data=data,
        meta=PaginationMeta(page=page, per_page=per_page, total=total, total_pages=total_pages),
    )


@router.get("/{order_id}", response_model=OrderDetail, summary="Детали заказа", description="Детальная информация о заказе. Для креатора — включает my_response если уже откликнулся.")
async def get_order(
    order_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Order).where(Order.id == order_id))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден")

    adv = await _build_advertiser_brief(db, order.advertiser_id)

    # Check if current user (creator) has responded
    my_response = None
    if user.role == "creator":
        resp_result = await db.execute(
            select(Response).where(Response.order_id == order.id, Response.creator_id == user.id)
        )
        resp = resp_result.scalar_one_or_none()
        if resp:
            my_response = {
                "id": str(resp.id),
                "status": resp.status,
                "created_at": resp.created_at.isoformat(),
            }

    return OrderDetail(
        id=str(order.id),
        advertiser=adv,
        title=order.title,
        description=order.description,
        budget=order.budget,
        currency=order.currency,
        deadline=order.deadline,
        platform=order.platform,
        content_type=order.content_type,
        content_count=order.content_count,
        content_duration_min=order.content_duration_min,
        content_duration_max=order.content_duration_max,
        categories=order.categories,
        city=order.city,
        status=order.status,
        response_count=order.response_count,
        created_at=order.created_at,
        my_response=my_response,
    )


@router.post("", response_model=OrderCreateResponse, status_code=status.HTTP_201_CREATED, summary="Создать заказ", description="Создание нового заказа. Только для рекламодателей.")
async def create_order(
    body: OrderCreateRequest,
    user: User = Depends(require_role("advertiser")),
    db: AsyncSession = Depends(get_db),
):
    order = Order(
        advertiser_id=user.id,
        title=body.title,
        description=body.description,
        budget=body.budget,
        currency=body.currency,
        deadline=body.deadline,
        platform=body.platform,
        content_type=body.content_type,
        content_count=body.content_count,
        content_duration_min=body.content_duration_min,
        content_duration_max=body.content_duration_max,
        categories=body.categories,
        city=body.city,
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    return OrderCreateResponse(
        id=str(order.id),
        title=order.title,
        status=order.status,
        created_at=order.created_at,
    )
