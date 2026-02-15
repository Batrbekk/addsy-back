from fastapi import APIRouter

from app.routers import (
    advertisers,
    auth,
    chats,
    creators,
    deals,
    notifications,
    offers,
    orders,
    profile,
    responses,
    reviews,
    tags,
    upload,
    ws,
)

api_router = APIRouter()

api_router.include_router(auth.router)
api_router.include_router(profile.router)
api_router.include_router(creators.router)
api_router.include_router(advertisers.router)
api_router.include_router(orders.router)
api_router.include_router(responses.router)
api_router.include_router(chats.router)
api_router.include_router(offers.router)
api_router.include_router(deals.router)
api_router.include_router(notifications.router)
api_router.include_router(reviews.router)
api_router.include_router(upload.router)
api_router.include_router(tags.router)
api_router.include_router(ws.router)
