import uuid
import datetime as dt
from pydantic import BaseModel


class ProjectCreate(BaseModel):
    name: str
    daily_query_quota: int = 200


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    daily_query_quota: int
    created_at: dt.datetime

    class Config:
        from_attributes = True
