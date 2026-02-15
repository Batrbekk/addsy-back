import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models.deal import Deal

CHECK_INTERVAL_SECONDS = 300  # 5 minutes


async def auto_complete_deals():
    """Background task: auto-complete deals where work_submitted_at + 24h has passed."""
    from app.core.database import async_session

    while True:
        try:
            async with async_session() as db:
                cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.WORK_REVIEW_PERIOD_HOURS)

                result = await db.execute(
                    select(Deal).where(
                        Deal.status == "work_submitted",
                        Deal.work_submitted_at != None,
                        Deal.work_submitted_at <= cutoff,
                    )
                )
                deals = result.scalars().all()

                for deal in deals:
                    fee = deal.budget * settings.PLATFORM_COMMISSION_PERCENT // 100
                    payout = deal.budget - fee

                    deal.status = "completed"
                    deal.platform_fee = fee
                    deal.creator_payout = payout

                    print(f"[AutoComplete] Deal {deal.id} auto-completed. Fee: {fee}, Payout: {payout}")

                if deals:
                    await db.commit()

        except Exception as e:
            print(f"[AutoComplete] Error: {e}")

        await asyncio.sleep(CHECK_INTERVAL_SECONDS)
