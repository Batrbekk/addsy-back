# AddSy Backend

REST API for AddSy — UGC creator marketplace in Kazakhstan. Connects advertisers with content creators for branded video content.

## Tech Stack

- **Framework:** FastAPI + Uvicorn
- **Database:** PostgreSQL 16 + SQLAlchemy 2.0 (async)
- **Auth:** JWT (access 30d + refresh 90d) + OTP via SMS (Mobizon)
- **Migrations:** Alembic
- **Real-time:** WebSocket chat
- **Tests:** pytest + pytest-asyncio (60 tests)
- **Deploy:** Docker Compose

## Features

- OTP authentication via SMS
- Creator & Advertiser profiles with search/filters
- Order feed with categories, budget, platform filters
- Real-time chat with WebSocket
- Offer system (send, view, accept, decline, cancel)
- Full deal flow: contract signing (SMS) → escrow payment → work submission → confirmation (24h auto-complete) → payout with 10% platform commission
- Dispute mechanism
- Review & rating system
- File uploads (avatar, portfolio, work)
- Background auto-complete service for deals

## Quick Start (Docker)

```bash
# 1. Clone & configure
cp .env.example .env
# Edit .env: set SECRET_KEY, MOBIZON_API_KEY

# 2. Run
docker compose up --build -d

# 3. Verify
curl http://localhost:8000/health
# → {"status":"ok"}

# API docs
open http://localhost:8000/docs
```

## Local Development

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set up PostgreSQL databases: addsy, addsy_test
# Configure .env

alembic upgrade head
uvicorn app.main:app --reload
```

## Tests

```bash
# Local
pytest tests/ -v

# Docker
docker compose exec backend pytest tests/ -v
```

## API Endpoints (49 routes)

| Group | Endpoints | Description |
|-------|-----------|-------------|
| Auth | 3 | OTP send/verify, token refresh |
| Profile | 3 | Get, set role, setup |
| Creators | 2 | Search, detail |
| Advertisers | 2 | Search, detail |
| Orders | 5 | CRUD, search, my orders |
| Responses | 4 | Create, list, my responses |
| Chats | 5 | Create, list, messages, offer, respond |
| Offers | 4 | Sent/received, view, cancel |
| Deals | 8 | List, detail, sign, pay, submit, confirm, dispute |
| Reviews | 2 | Create, get by user |
| Notifications | 2 | List, mark read |
| Tags | 1 | Categories, platforms, cities |
| Upload | 1 | File upload |
| WebSocket | 1 | Real-time chat |
| Health | 1 | Health check |

## Project Structure

```
backend/
├── app/
│   ├── core/           # config, database, security, deps
│   ├── models/         # SQLAlchemy ORM models
│   ├── schemas/        # Pydantic request/response schemas
│   ├── routers/        # API route handlers
│   └── services/       # Business logic (SMS, auto-complete)
├── alembic/            # Database migrations
├── tests/              # 60 tests across 11 files
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## Environment Variables

See [.env.example](.env.example) for all available variables. Required:

| Variable | Description |
|----------|-------------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SECRET_KEY` | JWT signing key (`openssl rand -hex 32`) |
| `MOBIZON_API_KEY` | SMS provider API key |

## License

Private. All rights reserved.
