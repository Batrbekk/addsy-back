from pydantic import BaseModel


class UploadResponse(BaseModel):
    url: str
    type: str
    size: int
    mime_type: str
