import os
import uuid

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status

from app.core.config import settings
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.upload import UploadResponse

router = APIRouter(prefix="/upload", tags=["Upload"])

ALLOWED_TYPES = {"avatar", "logo", "portfolio", "work"}


@router.post("", response_model=UploadResponse, status_code=status.HTTP_201_CREATED, summary="Загрузить файл", description="Загрузка файла (multipart/form-data). Типы: `avatar`, `logo`, `portfolio`, `work`. Макс. 50MB.")
async def upload_file(
    file: UploadFile = File(...),
    type: str = Form(...),
    _user: User = Depends(get_current_user),
):
    if type not in ALLOWED_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Неверный тип файла")

    if file.size and file.size > settings.MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Файл слишком большой (макс. 50MB)")

    ext = os.path.splitext(file.filename or "file")[1]
    filename = f"{uuid.uuid4()}{ext}"
    upload_dir = os.path.join(settings.UPLOAD_DIR, type)
    os.makedirs(upload_dir, exist_ok=True)

    filepath = os.path.join(upload_dir, filename)
    async with aiofiles.open(filepath, "wb") as f:
        content = await file.read()
        await f.write(content)

    return UploadResponse(
        url=f"/uploads/{type}/{filename}",
        type=type,
        size=len(content),
        mime_type=file.content_type or "application/octet-stream",
    )
