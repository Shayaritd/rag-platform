import uuid
import datetime as dt
from sqlalchemy import Column, String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.session import Base


class AuditLog(Base):
    """Append-only trail of sensitive actions (login, role change, doc delete, etc.)."""
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id"), nullable=False, index=True)
    actor_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    action = Column(String, nullable=False)          # e.g. "document.delete"
    resource_type = Column(String, nullable=False)   # e.g. "document"
    resource_id = Column(String, nullable=True)
    metadata_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
