import uuid
import datetime as dt
from pydantic import BaseModel


class DocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    status: str
    current_version: int
    size_bytes: int
    created_at: dt.datetime

    class Config:
        from_attributes = True


class IngestionStatusOut(BaseModel):
    document_id: uuid.UUID
    status: str
    attempt: int
    chunks_indexed: int
    error_message: str | None = None
