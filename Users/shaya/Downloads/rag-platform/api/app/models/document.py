import uuid
import datetime as dt
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, BigInteger
from sqlalchemy.dialects.postgresql import UUID

from app.db.session import Base


class Document(Base):
    __tablename__ = "documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    size_bytes = Column(BigInteger, nullable=False)
    storage_path = Column(String, nullable=False)
    current_version = Column(Integer, default=1)
    status = Column(String, default="uploaded")  # uploaded | processing | indexed | failed
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class DocumentVersion(Base):
    """Every re-upload of the same logical document creates a new version row,
    so old chunks can be diffed or rolled back without losing history."""
    __tablename__ = "document_versions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), ForeignKey("documents.id"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)
    storage_path = Column(String, nullable=False)
    checksum = Column(String, nullable=False)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
