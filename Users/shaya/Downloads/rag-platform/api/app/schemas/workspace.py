import uuid
import datetime as dt
from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=1)
    plan: str | None = None


class WorkspaceUpdate(BaseModel):
    name: str | None = None
    plan: str | None = None


class WorkspaceOut(BaseModel):
    id: uuid.UUID
    name: str
    plan: str
    created_at: dt.datetime

    class Config:
        from_attributes = True
