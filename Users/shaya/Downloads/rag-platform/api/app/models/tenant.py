import uuid
import datetime as dt
from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    plan = Column(String, default="free", nullable=False)  # free | pro | enterprise
    created_at = Column(DateTime, default=dt.datetime.utcnow)
