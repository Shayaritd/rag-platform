import hashlib
import os
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import CurrentUser, get_current_user
from app.db.session import get_db
from app.models import Document, DocumentVersion, IngestionJob, Project
from app.schemas.document import DocumentOut, IngestionStatusOut

try:
    from worker.tasks.ingestion import process_document
except ModuleNotFoundError:  # pragma: no cover - optional for tests
    def process_document(*args, **kwargs):
        return None

router = APIRouter(prefix="/api/v1/documents", tags=["documents"])
settings = get_settings()


def _workspace_project_or_404(db: Session, project_id: str, tenant_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.tenant_id == tenant_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/upload", response_model=DocumentOut, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    project_id: str | None = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Document:
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")

    _workspace_project_or_404(db, project_id, user.tenant_id)

    if file.content_type not in {"application/pdf", "text/plain"}:
        raise HTTPException(status_code=400, detail="Only PDF and TXT uploads are supported")

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_MB:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_UPLOAD_MB}MB limit")

    doc_id = uuid.uuid4()
    checksum = hashlib.sha256(contents).hexdigest()
    storage_path = os.path.join(settings.UPLOAD_DIR, str(project_id), f"{doc_id}.{'pdf' if file.content_type == 'application/pdf' else 'txt'}")
    os.makedirs(os.path.dirname(storage_path), exist_ok=True)
    with open(storage_path, "wb") as handle:
        handle.write(contents)

    document = Document(
        id=doc_id,
        project_id=project_id,
        filename=file.filename or "upload",
        content_type=file.content_type,
        size_bytes=len(contents),
        storage_path=storage_path,
        status="uploaded",
    )
    db.add(document)
    db.flush()

    db.add(DocumentVersion(document_id=doc_id, version_number=1, storage_path=storage_path, checksum=checksum))
    job = IngestionJob(document_id=doc_id, status="queued")
    db.add(job)
    db.commit()
    db.refresh(document)

    process_document.delay(str(doc_id), str(job.id))
    return document


@router.get("", response_model=list[DocumentOut])
def list_documents(
    project_id: str | None = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> list[Document]:
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")

    _workspace_project_or_404(db, project_id, user.tenant_id)
    return db.query(Document).filter(Document.project_id == project_id).all()


@router.get("/{document_id}/status", response_model=IngestionStatusOut)
def get_document_status(
    document_id: str,
    project_id: str | None = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> IngestionStatusOut:
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")

    _workspace_project_or_404(db, project_id, user.tenant_id)
    job = (
        db.query(IngestionJob)
        .filter(IngestionJob.document_id == document_id)
        .order_by(IngestionJob.created_at.desc())
        .first()
    )
    if not job:
        raise HTTPException(status_code=404, detail="No ingestion job found for this document")

    return IngestionStatusOut(
        document_id=document_id,
        status=job.status,
        attempt=job.attempt,
        chunks_indexed=job.chunks_indexed,
        error_message=job.error_message,
    )


@router.get("/{document_id}", response_model=DocumentOut)
def get_document(
    document_id: str,
    project_id: str | None = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Document:
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")

    _workspace_project_or_404(db, project_id, user.tenant_id)
    document = db.query(Document).filter(Document.id == document_id, Document.project_id == project_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_document(
    document_id: str,
    project_id: str | None = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> None:
    if not project_id:
        raise HTTPException(status_code=400, detail="project_id is required")

    _workspace_project_or_404(db, project_id, user.tenant_id)
    document = db.query(Document).filter(Document.id == document_id, Document.project_id == project_id).first()
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")

    db.query(DocumentVersion).filter(DocumentVersion.document_id == document.id).delete(synchronize_session=False)
    db.query(IngestionJob).filter(IngestionJob.document_id == document.id).delete(synchronize_session=False)
    db.delete(document)
    db.commit()
