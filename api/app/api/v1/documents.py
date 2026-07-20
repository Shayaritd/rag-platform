import os
import uuid
import hashlib
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Document, DocumentVersion, Project, IngestionJob
from app.schemas.document import DocumentOut, IngestionStatusOut
from app.core.security import get_current_user, CurrentUser
from app.core.config import get_settings
from app.celery_app import celery_app

router = APIRouter(prefix="/projects/{project_id}/documents", tags=["documents"])
settings = get_settings()


def _project_or_404(db: Session, project_id: str, tenant_id: str) -> Project:
    project = db.query(Project).filter(Project.id == project_id, Project.tenant_id == tenant_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("", response_model=DocumentOut, status_code=201)
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _project_or_404(db, project_id, user.tenant_id)

    if file.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="Only PDF uploads are supported")

    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_MB:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.MAX_UPLOAD_MB}MB limit")

    doc_id = uuid.uuid4()
    checksum = hashlib.sha256(contents).hexdigest()
    storage_path = os.path.join(settings.UPLOAD_DIR, str(project_id), f"{doc_id}.pdf")
    os.makedirs(os.path.dirname(storage_path), exist_ok=True)
    with open(storage_path, "wb") as f:
        f.write(contents)

    document = Document(
        id=doc_id, project_id=project_id, filename=file.filename, content_type=file.content_type,
        size_bytes=len(contents), storage_path=storage_path, status="uploaded",
    )
    db.add(document)
    db.flush()

    db.add(DocumentVersion(document_id=doc_id, version_number=1, storage_path=storage_path, checksum=checksum))
    job = IngestionJob(document_id=doc_id, status="queued")
    db.add(job)
    db.commit()

    celery_app.send_task("worker.tasks.ingestion.process_document", args=[str(doc_id), str(job.id)])  # hand off to Celery, don't block the request
    return document


@router.get("", response_model=list[DocumentOut])
def list_documents(project_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    _project_or_404(db, project_id, user.tenant_id)
    return db.query(Document).filter(Document.project_id == project_id).all()


@router.get("/{document_id}/status", response_model=IngestionStatusOut)
def ingestion_status(project_id: str, document_id: str, db: Session = Depends(get_db), user: CurrentUser = Depends(get_current_user)):
    _project_or_404(db, project_id, user.tenant_id)
    job = db.query(IngestionJob).filter(IngestionJob.document_id == document_id).order_by(IngestionJob.created_at.desc()).first()
    if not job:
        raise HTTPException(status_code=404, detail="No ingestion job found for this document")
    return IngestionStatusOut(document_id=document_id, status=job.status, attempt=job.attempt,
                               chunks_indexed=job.chunks_indexed, error_message=job.error_message)
