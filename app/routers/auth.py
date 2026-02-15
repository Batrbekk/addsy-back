from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token, decode_token, generate_otp
from app.models.otp import OTPCode
from app.models.user import User
from app.schemas.auth import (
    ErrorResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    SendOTPRequest,
    SendOTPResponse,
    UserBrief,
    VerifyOTPRequest,
    VerifyOTPResponse,
)
from app.core.config import settings

router = APIRouter(prefix="/auth", tags=["Auth"])


@router.post(
    "/send-otp",
    response_model=SendOTPResponse,
    responses={429: {"model": ErrorResponse, "description": "Rate limit — 1 запрос в 60 сек на номер"}},
    summary="Отправить OTP-код",
    description="Отправляет 6-значный SMS-код через Mobizon. Формат номера: `+7XXXXXXXXXX`. Код живёт 5 минут. Rate limit: 1 запрос в 60 секунд на номер.",
)
async def send_otp(body: SendOTPRequest, db: AsyncSession = Depends(get_db)):
    # Rate limit: check last OTP for this phone
    result = await db.execute(
        select(OTPCode)
        .where(OTPCode.phone == body.phone, OTPCode.is_used == False)
        .order_by(OTPCode.created_at.desc())
        .limit(1)
    )
    last_otp = result.scalar_one_or_none()

    if last_otp:
        seconds_since = (datetime.now(timezone.utc) - last_otp.created_at).total_seconds()
        if seconds_since < settings.OTP_RATE_LIMIT_SECONDS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Подождите {int(settings.OTP_RATE_LIMIT_SECONDS - seconds_since)} секунд",
            )

    code = generate_otp()
    otp = OTPCode(
        phone=body.phone,
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=settings.OTP_EXPIRE_MINUTES),
    )
    db.add(otp)
    await db.commit()

    # Send SMS via Mobizon
    from app.services.sms import send_otp_sms

    sent = await send_otp_sms(body.phone, code)
    if not sent:
        print(f"[OTP] Mobizon failed, fallback log — {body.phone}: {code}")

    return SendOTPResponse()


@router.post(
    "/verify-otp",
    response_model=VerifyOTPResponse,
    responses={400: {"model": ErrorResponse, "description": "Неверный или истёкший код"}},
    summary="Верификация OTP-кода",
    description="Проверяет OTP-код. Если пользователь новый — создаёт запись. Возвращает `token` (30 дней) и `refresh_token` (90 дней). Если `role == null` — клиент показывает экран выбора роли.",
)
async def verify_otp(body: VerifyOTPRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(OTPCode).where(
            OTPCode.phone == body.phone,
            OTPCode.code == body.code,
            OTPCode.is_used == False,
            OTPCode.expires_at > datetime.now(timezone.utc),
        )
    )
    otp = result.scalar_one_or_none()

    if not otp:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный или истёкший код")

    otp.is_used = True

    # Find or create user
    result = await db.execute(select(User).where(User.phone == body.phone))
    user = result.scalar_one_or_none()

    if not user:
        user = User(phone=body.phone)
        db.add(user)

    await db.commit()
    await db.refresh(user)

    token = create_access_token(str(user.id))
    refresh = create_refresh_token(str(user.id))

    return VerifyOTPResponse(
        token=token,
        refresh_token=refresh,
        user=UserBrief(
            id=str(user.id),
            phone=user.phone,
            role=user.role,
            name=user.name,
            avatar_url=user.avatar_url,
            is_profile_complete=user.is_profile_complete,
        ),
    )


@router.post(
    "/refresh",
    response_model=RefreshTokenResponse,
    responses={401: {"model": ErrorResponse, "description": "Неверный refresh token"}},
    summary="Обновить токены",
    description="Выдаёт новую пару `token` + `refresh_token` по действующему refresh_token.",
)
async def refresh_token(body: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(body.refresh_token)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный refresh token")

    user_id = payload.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Пользователь не найден")

    return RefreshTokenResponse(
        token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )
