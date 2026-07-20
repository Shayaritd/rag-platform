import uuid
import datetime as dt
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Float, Text
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base


class QueryLog(Base):
    """Powers usage tracking: per-user/per-project quotas, token estimates, latency."""
    __tablename__ = "query_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    question = Column(Text, nullable=False)
    provider_used = Column(String, nullable=False)  # gemini | llama
    latency_ms = Column(Integer, nullable=False)
    prompt_tokens_est = Column(Integer, default=0)
    completion_tokens_est = Column(Integer, default=0)
    cache_hit = Column(String, default="false")
    created_at = Column(DateTime, default=dt.datetime.utcnow)
