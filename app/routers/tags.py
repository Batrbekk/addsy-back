from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.order import Order
from app.models.user import CreatorProfile, User

router = APIRouter(prefix="/tags", tags=["Tags"])


@router.get(
    "",
    summary="Список тегов/категорий",
    description="Возвращает все доступные категории из заказов и профилей креаторов. Используется для фильтрации и автокомплита.",
)
async def list_tags(
    _user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Categories from orders
    order_cats = await db.execute(
        select(func.unnest(Order.categories)).distinct()
    )
    order_tags = {row[0] for row in order_cats.all() if row[0]}

    # Categories from creator profiles
    creator_cats = await db.execute(
        select(func.unnest(CreatorProfile.categories)).distinct()
    )
    creator_tags = {row[0] for row in creator_cats.all() if row[0]}

    all_tags = sorted(order_tags | creator_tags)

    # Industries from advertiser profiles
    from app.models.user import AdvertiserProfile
    industries_result = await db.execute(
        select(AdvertiserProfile.industry).distinct().where(AdvertiserProfile.industry != None)
    )
    industries = sorted([row[0] for row in industries_result.all() if row[0]])

    # Platforms from orders
    platforms_result = await db.execute(
        select(Order.platform).distinct().where(Order.platform != None)
    )
    platforms = sorted([row[0] for row in platforms_result.all() if row[0]])

    # Cities from orders + creator profiles
    order_cities = await db.execute(
        select(Order.city).distinct().where(Order.city != None)
    )
    creator_cities = await db.execute(
        select(CreatorProfile.city).distinct().where(CreatorProfile.city != None)
    )
    cities = sorted(
        {row[0] for row in order_cities.all() if row[0]}
        | {row[0] for row in creator_cities.all() if row[0]}
    )

    return {
        "categories": all_tags,
        "industries": industries,
        "platforms": platforms,
        "cities": cities,
    }
