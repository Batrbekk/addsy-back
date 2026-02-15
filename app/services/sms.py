import httpx

from app.core.config import settings


async def send_sms(phone: str, text: str) -> bool:
    """Send SMS via Mobizon API. Phone format: +77771234567 -> 77771234567"""
    recipient = phone.lstrip("+")

    params = {
        "recipient": recipient,
        "text": text,
        "apiKey": settings.MOBIZON_API_KEY,
        "output": "json",
        "api": "v1",
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{settings.MOBIZON_API_URL}/message/sendsmsmessage",
                params=params,
            )
            data = resp.json()
            if data.get("code") == 0:
                return True
            print(f"[Mobizon] Error: {data.get('message', 'Unknown error')}")
            return False
    except Exception as e:
        print(f"[Mobizon] Request failed: {e}")
        return False


async def send_otp_sms(phone: str, code: str) -> bool:
    """Send OTP code via SMS."""
    text = f"AddSy: ваш код подтверждения {code}. Не сообщайте его никому."
    return await send_sms(phone, text)
