import uuid
import datetime as dt
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base


class Project(Base):
    __tablename__ = "projects"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    name = Column(String, nullable=False)
    qdrant_collection = Column(String, nullable=False)  # tenant_<id>_project_<id>
    daily_query_quota = Column(Integer, default=200)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
