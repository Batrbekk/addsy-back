import random
import string
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_role
from app.models.deal import Deal, DealSignature, SubmittedWork, WorkRequirement
from app.models.order import Order
from app.models.user import AdvertiserProfile, CreatorProfile, User
from app.schemas.deal import (
    ConfirmWorkResponse,
    ContractInfo,
    DealAdvertiserBrief,
    DealCreatorBrief,
    DealDetail,
    DealListItem,
    DealListResponse,
    DealOrderBrief,
    DisputeDealRequest,
    DisputeDealResponse,
    PayDealRequest,
    PayDealResponse,
    PaymentInfo,
    PayoutInfo,
    RequestSignResponse,
    SignatureItem,
    SignDealRequest,
    SignDealResponse,
    SubmitWorkResponse,
    SubmittedWorkItem,
    WorkRequirementItem,
)
from app.services.sms import send_sms

router = APIRouter(prefix="/deals", tags=["Deals"])


def _generate_sms_code() -> str:
    return "".join(random.choices(string.digits, k=6))


async def _deal_creator_brief(db: AsyncSession, creator_id) -> DealCreatorBrief:
    result = await db.execute(select(User).where(User.id == creator_id))
    u = result.scalar_one_or_none()
    return DealCreatorBrief(id=str(creator_id), name=u.name if u else None, avatar_url=u.avatar_url if u else None)


async def _deal_advertiser_brief(db: AsyncSession, advertiser_id) -> DealAdvertiserBrief:
    result = await db.execute(select(AdvertiserProfile).where(AdvertiserProfile.user_id == advertiser_id))
    p = result.scalar_one_or_none()
    return DealAdvertiserBrief(
        id=str(advertiser_id), company_name=p.company_name if p else None, logo_url=p.logo_url if p else None
    )


async def _get_user_deal(db: AsyncSession, deal_id: str, user_id) -> Deal:
    result = await db.execute(
        select(Deal).where(
            Deal.id == deal_id,
            or_(Deal.creator_id == user_id, Deal.advertiser_id == user_id),
        )
    )
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сделка не найдена")
    return deal


# ──────────────────────────────────────────────
# LIST / DETAIL
# ──────────────────────────────────────────────

@router.get(
    "",
    response_model=DealListResponse,
    summary="Список сделок",
    description="Все сделки текущего пользователя (как креатор или рекламодатель). Фильтр по статусу.",
)
async def list_deals(
    deal_status: str | None = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = select(Deal).where(or_(Deal.creator_id == user.id, Deal.advertiser_id == user.id))
    if deal_status:
        query = query.where(Deal.status == deal_status)
    query = query.order_by(Deal.created_at.desc())

    result = await db.execute(query)
    deals = result.scalars().all()

    data = []
    for deal in deals:
        order_result = await db.execute(select(Order).where(Order.id == deal.order_id))
        order = order_result.scalar_one_or_none()

        data.append(
            DealListItem(
                id=str(deal.id),
                order=DealOrderBrief(id=str(deal.order_id), title=order.title if order else ""),
                creator=await _deal_creator_brief(db, deal.creator_id),
                advertiser=await _deal_advertiser_brief(db, deal.advertiser_id),
                budget=deal.budget,
                currency=deal.currency,
                deadline=deal.deadline,
                conditions=deal.conditions,
                start_date=deal.start_date,
                end_date=deal.end_date,
                video_count=deal.video_count,
                status=deal.status,
                created_at=deal.created_at,
            )
        )

    return DealListResponse(data=data)


@router.get(
    "/{deal_id}",
    response_model=DealDetail,
    summary="Детали сделки",
    description="Полная информация о сделке: договор, подписи, требования, сданные работы, статус оплаты, комиссия.",
)
async def get_deal(
    deal_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deal = await _get_user_deal(db, deal_id, user.id)

    order_result = await db.execute(select(Order).where(Order.id == deal.order_id))
    order = order_result.scalar_one_or_none()

    # Signatures
    sig_result = await db.execute(select(DealSignature).where(DealSignature.deal_id == deal.id))
    signatures = sig_result.scalars().all()
    sig_items = []
    for sig in signatures:
        u_result = await db.execute(select(User).where(User.id == sig.user_id))
        u = u_result.scalar_one_or_none()
        sig_items.append(
            SignatureItem(
                user_id=str(sig.user_id),
                name=u.name if u else None,
                role=u.role if u else None,
                status=sig.status,
                signed_at=sig.signed_at,
            )
        )

    # Work requirements
    req_result = await db.execute(
        select(WorkRequirement).where(WorkRequirement.deal_id == deal.id).order_by(WorkRequirement.sort_order)
    )
    requirements = req_result.scalars().all()

    # Submitted work
    work_result = await db.execute(select(SubmittedWork).where(SubmittedWork.deal_id == deal.id))
    submitted = work_result.scalars().all()

    # Payment status
    if deal.paid_at:
        payment_status = "paid"
    elif deal.escrow_amount > 0:
        payment_status = "held"
    else:
        payment_status = "pending"

    return DealDetail(
        id=str(deal.id),
        order=DealOrderBrief(
            id=str(deal.order_id),
            title=order.title if order else "",
            content_description=order.description if order else None,
        ),
        creator=await _deal_creator_brief(db, deal.creator_id),
        advertiser=await _deal_advertiser_brief(db, deal.advertiser_id),
        budget=deal.budget,
        currency=deal.currency,
        deadline=deal.deadline,
        conditions=deal.conditions,
        start_date=deal.start_date,
        end_date=deal.end_date,
        video_count=deal.video_count,
        status=deal.status,
        created_at=deal.created_at,
        contract=ContractInfo(signatures=sig_items),
        work_requirements=[
            WorkRequirementItem(id=str(r.id), label=r.label, is_completed=r.is_completed) for r in requirements
        ],
        submitted_work=[
            SubmittedWorkItem(
                id=str(w.id), title=w.title, file_url=w.file_url, duration=w.duration, format=w.format, uploaded_at=w.uploaded_at
            )
            for w in submitted
        ],
        escrow_amount=deal.escrow_amount,
        platform_fee=deal.platform_fee,
        creator_payout=deal.creator_payout,
        payment_status=payment_status,
        work_submitted_at=deal.work_submitted_at,
        dispute_reason=deal.dispute_reason,
    )


# ──────────────────────────────────────────────
# CONTRACT SIGNING (SMS)
# ──────────────────────────────────────────────

@router.post(
    "/{deal_id}/request-sign",
    response_model=RequestSignResponse,
    summary="Запросить SMS-код для подписания",
    description="Генерирует 6-значный SMS-код и отправляет на номер пользователя для подписания договора.",
)
async def request_sign(
    deal_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deal = await _get_user_deal(db, deal_id, user.id)

    if deal.status not in ("contract_pending", "contract_signed"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Договор нельзя подписать в текущем статусе")

    # Check if already signed
    sig_result = await db.execute(
        select(DealSignature).where(DealSignature.deal_id == deal.id, DealSignature.user_id == user.id)
    )
    sig = sig_result.scalar_one_or_none()
    if sig and sig.status == "signed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Вы уже подписали договор")

    # Generate SMS code
    code = _generate_sms_code()
    now = datetime.now(timezone.utc)

    if not sig:
        sig = DealSignature(deal_id=deal.id, user_id=user.id, sms_code=code, sms_sent_at=now)
        db.add(sig)
    else:
        sig.sms_code = code
        sig.sms_sent_at = now

    await db.commit()

    # Send SMS
    sms_text = f"AddSy: код для подписания договора: {code}. Не сообщайте его никому."
    sent = await send_sms(user.phone, sms_text)
    if not sent:
        print(f"[Deal Sign] SMS failed for {user.phone}, code: {code}")

    return RequestSignResponse(deal_id=str(deal.id))


@router.post(
    "/{deal_id}/sign",
    response_model=SignDealResponse,
    summary="Подписать договор SMS-кодом",
    description="Подписание договора через SMS-код. Когда обе стороны подписали — статус переходит в `pending_payment`.",
)
async def sign_deal(
    deal_id: str,
    body: SignDealRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    deal = await _get_user_deal(db, deal_id, user.id)

    if deal.status not in ("contract_pending", "contract_signed"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Договор нельзя подписать в текущем статусе")

    # Find signature record
    sig_result = await db.execute(
        select(DealSignature).where(DealSignature.deal_id == deal.id, DealSignature.user_id == user.id)
    )
    sig = sig_result.scalar_one_or_none()
    if not sig:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Сначала запросите SMS-код")

    if sig.status == "signed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Вы уже подписали договор")

    # Verify SMS code
    if sig.sms_code != body.code:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный SMS-код")

    sig.status = "signed"
    sig.signed_at = datetime.now(timezone.utc)
    sig.sms_code = None  # Clear after use

    # Check if both parties signed
    all_sigs = await db.execute(select(DealSignature).where(DealSignature.deal_id == deal.id))
    all_sigs_list = all_sigs.scalars().all()

    party_ids = {deal.creator_id, deal.advertiser_id}
    signed_ids = {s.user_id for s in all_sigs_list if s.status == "signed"}
    signed_ids.add(user.id)

    if party_ids <= signed_ids:
        deal.status = "pending_payment"
    else:
        deal.status = "contract_signed"

    await db.commit()

    return SignDealResponse(deal_id=str(deal.id), signature_status="signed", deal_status=deal.status)


# ──────────────────────────────────────────────
# PAYMENT (ESCROW)
# ──────────────────────────────────────────────

@router.post(
    "/{deal_id}/pay",
    response_model=PayDealResponse,
    summary="Оплатить (рекламодатель)",
    description="Рекламодатель оплачивает сделку после подписания договора обеими сторонами. Деньги уходят на эскроу. Статус — `in_progress`.",
)
async def pay_deal(
    deal_id: str,
    body: PayDealRequest,
    user: User = Depends(require_role("advertiser")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Deal).where(Deal.id == deal_id, Deal.advertiser_id == user.id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сделка не найдена")

    if deal.status != "pending_payment":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Оплата возможна только после подписания договора обеими сторонами")

    now = datetime.now(timezone.utc)
    deal.status = "in_progress"
    deal.escrow_amount = deal.budget
    deal.payment_method = body.payment_method
    deal.paid_at = now
    await db.commit()

    return PayDealResponse(
        deal_id=str(deal.id),
        status="in_progress",
        escrow_amount=deal.escrow_amount,
        payment=PaymentInfo(amount=deal.budget, currency=deal.currency, method=body.payment_method, paid_at=now),
    )


# ──────────────────────────────────────────────
# WORK SUBMISSION (CREATOR)
# ──────────────────────────────────────────────

@router.post(
    "/{deal_id}/submit-work",
    response_model=SubmitWorkResponse,
    summary="Сдать работу (креатор)",
    description="Креатор отмечает работу как сданную. Запускается таймер 24 часа для подтверждения рекламодателем.",
)
async def submit_work(
    deal_id: str,
    user: User = Depends(require_role("creator")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Deal).where(Deal.id == deal_id, Deal.creator_id == user.id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сделка не найдена")

    if deal.status != "in_progress":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Нельзя сдать работу в текущем статусе")

    now = datetime.now(timezone.utc)
    deal.status = "work_submitted"
    deal.work_submitted_at = now
    await db.commit()

    work_result = await db.execute(select(SubmittedWork).where(SubmittedWork.deal_id == deal.id))
    submitted = work_result.scalars().all()

    return SubmitWorkResponse(
        deal_id=str(deal.id),
        status=deal.status,
        work_submitted_at=deal.work_submitted_at,
        submitted_work=[
            SubmittedWorkItem(
                id=str(w.id), title=w.title, file_url=w.file_url, duration=w.duration, format=w.format, uploaded_at=w.uploaded_at
            )
            for w in submitted
        ],
    )


# ──────────────────────────────────────────────
# CONFIRM WORK (ADVERTISER)
# ──────────────────────────────────────────────

@router.post(
    "/{deal_id}/confirm-work",
    response_model=ConfirmWorkResponse,
    summary="Подтвердить работу (рекламодатель)",
    description="Рекламодатель подтверждает выполненную работу. Рассчитывается комиссия платформы (10%%). Деньги переводятся креатору.",
)
async def confirm_work(
    deal_id: str,
    user: User = Depends(require_role("advertiser")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Deal).where(Deal.id == deal_id, Deal.advertiser_id == user.id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сделка не найдена")

    if deal.status != "work_submitted":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Работа ещё не сдана")

    # Calculate commission
    fee = deal.budget * settings.PLATFORM_COMMISSION_PERCENT // 100
    payout = deal.budget - fee

    deal.status = "completed"
    deal.platform_fee = fee
    deal.creator_payout = payout
    await db.commit()

    return ConfirmWorkResponse(
        deal_id=str(deal.id),
        status="completed",
        payout=PayoutInfo(budget=deal.budget, platform_fee=fee, creator_payout=payout, currency=deal.currency),
    )


# ──────────────────────────────────────────────
# DISPUTE (ADVERTISER)
# ──────────────────────────────────────────────

@router.post(
    "/{deal_id}/dispute",
    response_model=DisputeDealResponse,
    summary="Оспорить работу (рекламодатель)",
    description="Рекламодатель оспаривает работу креатора. Сделка переходит в статус `disputed` и направляется на модерацию.",
)
async def dispute_deal(
    deal_id: str,
    body: DisputeDealRequest,
    user: User = Depends(require_role("advertiser")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Deal).where(Deal.id == deal_id, Deal.advertiser_id == user.id))
    deal = result.scalar_one_or_none()
    if not deal:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Сделка не найдена")

    if deal.status != "work_submitted":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Оспорить можно только сданную работу")

    deal.status = "disputed"
    deal.dispute_reason = body.reason
    await db.commit()

    return DisputeDealResponse(deal_id=str(deal.id), status="disputed", reason=body.reason)
