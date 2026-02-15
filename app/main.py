import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.staticfiles import StaticFiles

from app.core.config import settings
from app.routers import api_router
from app.services.auto_complete import auto_complete_deals

TAGS_METADATA = [
    {"name": "Auth", "description": "OTP-авторизация по номеру телефона (Казахстан). SMS через Mobizon."},
    {"name": "Profile", "description": "Получение, выбор роли и настройка профиля пользователя."},
    {"name": "Creators", "description": "Поиск и просмотр профилей UGC-креаторов."},
    {"name": "Orders", "description": "Лента заказов, создание, детали. Рекламодатели создают — креаторы откликаются."},
    {"name": "Advertisers", "description": "Поиск и просмотр профилей рекламодателей."},
    {"name": "Responses", "description": "Отклики креаторов на заказы рекламодателей."},
    {"name": "Chats", "description": "REST API чатов: список, создание, сообщения, офферы. Для real-time используйте WebSocket."},
    {"name": "Offers", "description": "Офферы: отправленные и полученные, статусы (pending, viewed, accepted, declined, cancelled), просмотр, отмена."},
    {"name": "Deals", "description": "Сделки: подписание договора через SMS, оплата на эскроу, сдача работы, подтверждение (24ч таймер), диспут, комиссия 10%."},
    {"name": "Notifications", "description": "Уведомления пользователя."},
    {"name": "Reviews", "description": "Отзывы между креаторами и рекламодателями после завершения сделки."},
    {"name": "Upload", "description": "Загрузка файлов (аватар, логотип, портфолио, работа)."},
    {"name": "Tags", "description": "Список доступных категорий, отраслей, платформ, городов для фильтрации."},
    {"name": "WebSocket", "description": "Real-time чат через WebSocket."},
]

WS_DESCRIPTION = """
# AddSy API

Бэкенд мобильного приложения AddSy — маркетплейс для UGC-креаторов и рекламодателей в Казахстане.

## Авторизация

Все запросы (кроме `/auth/*`) требуют заголовок:
```
Authorization: Bearer <token>
```
Токен живёт **30 дней**. После истечения — используйте `POST /v1/auth/refresh` с `refresh_token`.

## Флоу регистрации

```
POST /auth/send-otp        → SMS с 6-значным кодом
POST /auth/verify-otp      → token + refresh_token + user
  ├─ user.role == null      → POST /profile (выбор роли)
  ├─ is_profile_complete    → false → PUT /profile/setup
  └─ is_profile_complete    → true  → Home
```

## WebSocket — Real-time чат

**Подключение:**
```
ws://localhost:8000/v1/ws?token=<jwt_access_token>
```

**Отправка сообщения:**
```json
{"action": "send_message", "chat_id": "uuid", "content": "Привет!", "type": "text"}
```

**Индикатор набора:**
```json
{"action": "typing", "chat_id": "uuid"}
```

**Отметить прочитанным:**
```json
{"action": "read", "chat_id": "uuid"}
```

**Входящие события от сервера:**

`new_message`:
```json
{"event": "new_message", "data": {"id": "uuid", "chat_id": "uuid", "sender_id": "uuid", "type": "text", "content": "Привет!", "created_at": "2025-01-13T14:32:00Z"}}
```

`typing`:
```json
{"event": "typing", "data": {"chat_id": "uuid", "user_id": "uuid"}}
```

`messages_read`:
```json
{"event": "messages_read", "data": {"chat_id": "uuid", "read_by": "uuid", "read_at": "2025-01-13T14:32:00Z"}}
```
"""

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(auto_complete_deals())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=WS_DESCRIPTION,
    openapi_tags=TAGS_METADATA,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)

app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR, check_dir=False), name="uploads")


@app.get("/health", tags=["Health"])
async def health():
    """Проверка работоспособности сервера."""
    return {"status": "ok"}
