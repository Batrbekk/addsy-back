from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.order import Order
from app.models.response import Response
from app.models.user import AdvertiserProfile, CreatorProfile, User
from app.schemas.response import (
    AdvertiserBrief,
    CreateResponseRequest,
    CreatorBrief,
    MyResponseItem,
    MyResponsesListResponse,
    OrderBrief,
    OrderResponseItem,
    OrderResponsesListResponse,
    ResponseCreated,
)

router = APIRouter(tags=["Responses"])


@router.post("/orders/{order_id}/responses", response_model=ResponseCreated, status_code=status.HTTP_201_CREATED, summary="Откликнуться на заказ", description="Креатор откликается на заказ. Можно указать сообщение и предложенную цену. Один отклик на заказ.")
async def create_response(
    order_id: str,
    body: CreateResponseRequest,
    user: User = Depends(require_role("creator")),
    db: AsyncSession = Depends(get_db),
):
    # Check order exists
    result = await db.execute(select(Order).where(Order.id == order_id, Order.status == "active"))
    order = result.scalar_one_or_none()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден")

    # Check duplicate
    existing = await db.execute(
        select(Response).where(Response.order_id == order_id, Response.creator_id == user.id)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Вы уже откликнулись на этот заказ")

    response = Response(
        order_id=order.id,
        creator_id=user.id,
        message=body.message,
        proposed_price=body.proposed_price,
    )
    db.add(response)

    order.response_count += 1
    await db.commit()
    await db.refresh(response)

    return ResponseCreated(
        id=str(response.id),
        order_id=str(response.order_id),
        status=response.status,
        created_at=response.created_at,
    )


@router.get("/orders/my/responses", response_model=MyResponsesListResponse, summary="Мои отклики (креатор)", description="Список откликов текущего креатора на заказы.")
async def my_responses(
    user: User = Depends(require_role("creator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Response, Order)
        .join(Order, Order.id == Response.order_id)
        .where(Response.creator_id == user.id)
        .order_by(Response.created_at.desc())
    )
    rows = result.all()

    data = []
    for resp, order in rows:
        # Get advertiser info
        adv_result = await db.execute(select(AdvertiserProfile).where(AdvertiserProfile.user_id == order.advertiser_id))
        adv = adv_result.scalar_one_or_none()

        data.append(
            MyResponseItem(
                id=str(resp.id),
                order=OrderBrief(
                    id=str(order.id),
                    title=order.title,
                    advertiser=AdvertiserBrief(
                        company_name=adv.company_name if adv else None,
                        logo_url=adv.logo_url if adv else None,
                    ),
                    budget=order.budget,
                    currency=order.currency,
                ),
                status=resp.status,
                created_at=resp.created_at,
            )
        )

    return MyResponsesListResponse(data=data)


@router.get("/orders/{order_id}/responses", response_model=OrderResponsesListResponse, summary="Отклики на заказ (рекламодатель)", description="Список откликов креаторов на конкретный заказ. Только для владельца заказа.")
async def order_responses(
    order_id: str,
    user: User = Depends(require_role("advertiser")),
    db: AsyncSession = Depends(get_db),
):
    # Verify ownership
    result = await db.execute(select(Order).where(Order.id == order_id, Order.advertiser_id == user.id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заказ не найден")

    result = await db.execute(
        select(Response, User, CreatorProfile)
        .join(User, User.id == Response.creator_id)
        .outerjoin(CreatorProfile, CreatorProfile.user_id == User.id)
        .where(Response.order_id == order_id)
        .order_by(Response.created_at.desc())
    )
    rows = result.all()

    data = []
    for resp, creator_user, profile in rows:
        data.append(
            OrderResponseItem(
                id=str(resp.id),
                creator=CreatorBrief(
                    id=str(creator_user.id),
                    name=creator_user.name,
                    avatar_url=creator_user.avatar_url,
                    rating=profile.rating if profile else None,
                    categories=profile.categories if profile else None,
                ),
                message=resp.message,
                proposed_price=resp.proposed_price,
                status=resp.status,
                created_at=resp.created_at,
            )
        )

    return OrderResponsesListResponse(data=data)
