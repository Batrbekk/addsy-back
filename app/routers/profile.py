from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import AdvertiserProfile, CreatorProfile, User
from app.schemas.profile import (
    AdvertiserSetupRequest,
    CreatorSetupRequest,
    ProfileResponse,
    SetRoleRequest,
)

router = APIRouter(prefix="/profile", tags=["Profile"])


def _profile_response(user: User) -> ProfileResponse:
    return ProfileResponse(
        id=str(user.id),
        phone=user.phone,
        role=user.role,
        name=user.name,
        avatar_url=user.avatar_url,
        is_profile_complete=user.is_profile_complete,
    )


@router.get("", response_model=ProfileResponse, summary="Получить профиль", description="Возвращает профиль текущего пользователя. Используйте `role` и `is_profile_complete` для определения куда направить пользователя.")
async def get_profile(user: User = Depends(get_current_user)):
    return _profile_response(user)


@router.post("", response_model=ProfileResponse, summary="Выбор роли", description="Устанавливает роль пользователя: `creator` или `advertiser`. Вызывается один раз после первой авторизации. После выбора роли — клиент направляет на заполнение профиля.")
async def set_role(
    body: SetRoleRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Роль уже установлена")

    user.role = body.role
    await db.commit()
    await db.refresh(user)
    return _profile_response(user)


@router.put("/setup", response_model=ProfileResponse, summary="Настройка профиля", description="Заполнение профиля после выбора роли. Для **creator**: name, bio, city, instagram, tiktok, categories. Для **advertiser**: company_name, industry, city, about, website, logo_url. После успешного заполнения `is_profile_complete = true`.")
async def setup_profile(
    body: dict,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if user.role is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Сначала выберите роль")

    if user.role == "creator":
        data = CreatorSetupRequest(**body)
        user.name = data.name
        user.avatar_url = data.avatar_url

        profile = await _get_or_create_creator_profile(db, user)
        profile.bio = data.bio
        profile.city = data.city
        profile.instagram = data.instagram
        profile.tiktok = data.tiktok
        profile.categories = data.categories

    elif user.role == "advertiser":
        data = AdvertiserSetupRequest(**body)
        user.name = data.company_name
        user.avatar_url = data.logo_url

        profile = await _get_or_create_advertiser_profile(db, user)
        profile.company_name = data.company_name
        profile.industry = data.industry
        profile.city = data.city
        profile.about = data.about
        profile.website = data.website
        profile.logo_url = data.logo_url
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверная роль")

    user.is_profile_complete = True
    await db.commit()
    await db.refresh(user)
    return _profile_response(user)


async def _get_or_create_creator_profile(db: AsyncSession, user: User) -> CreatorProfile:
    from sqlalchemy import select

    result = await db.execute(select(CreatorProfile).where(CreatorProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = CreatorProfile(user_id=user.id)
        db.add(profile)
    return profile


async def _get_or_create_advertiser_profile(db: AsyncSession, user: User) -> AdvertiserProfile:
    from sqlalchemy import select

    result = await db.execute(select(AdvertiserProfile).where(AdvertiserProfile.user_id == user.id))
    profile = result.scalar_one_or_none()
    if not profile:
        profile = AdvertiserProfile(user_id=user.id)
        db.add(profile)
    return profile
