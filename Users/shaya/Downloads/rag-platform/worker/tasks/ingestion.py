"""
Async ingestion pipeline: extract -> chunk -> enrich metadata -> embed -> index.
Each stage updates the IngestionJob row so the dashboard can show live status.
Retries use Celery's autoretry with exponential backoff; after max_attempts
the job is marked 'failed' and surfaced in the dashboard + Prometheus counter.
"""
import datetime as dt
import uuid
import fitz  # PyMuPDF
from celery import shared_task
from celery.utils.log import get_task_logger

from app.db.session import SessionLocal
from app.models import Document, IngestionJob, Project
from app.services.embeddings import get_embedder
from app.services import vector_store

logger = get_task_logger(__name__)

CHUNK_SIZE_CHARS = 1200
CHUNK_OVERLAP_CHARS = 200


def extract_text_per_page(pdf_path: str) -> list[tuple[int, str]]:
    doc = fitz.open(pdf_path)
    pages = [(i + 1, page.get_text()) for i, page in enumerate(doc)]
    doc.close()
    return pages


def chunk_text(pages: list[tuple[int, str]]) -> list[dict]:
    chunks = []
    for page_num, text in pages:
        start = 0
        while start < len(text):
            end = start + CHUNK_SIZE_CHARS
            piece = text[start:end].strip()
            if piece:
                chunks.append({"text": piece, "page": page_num})
            start = end - CHUNK_OVERLAP_CHARS
    return chunks


@shared_task(name="worker.tasks.ingestion.process_document", bind=True, max_retries=3, default_retry_delay=15)
def process_document(self, document_id: str, job_id: str):
    db = SessionLocal()
    try:
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        document = db.query(Document).filter(Document.id == document_id).first()
        project = db.query(Project).filter(Project.id == document.project_id).first()

        job.status = "extracting"
        job.started_at = dt.datetime.utcnow()
        job.attempt += 1
        document.status = "processing"
        db.commit()

        pages = extract_text_per_page(document.storage_path)

        job.status = "chunking"
        db.commit()
        chunks = chunk_text(pages)

        job.status = "embedding"
        db.commit()
        embedder = get_embedder()
        vectors = embedder.embed([c["text"] for c in chunks])

        job.status = "indexing"
        db.commit()
        points = [
            {
                "id": str(uuid.uuid4()),
                "vector": vectors[i],
                "payload": {
                    "text": chunks[i]["text"],
                    "page": chunks[i]["page"],
                    "document_id": str(document_id),
                    "filename": document.filename,
                },
            }
            for i in range(len(chunks))
        ]
        vector_store.upsert_chunks(project.qdrant_collection, points)

        job.status = "done"
        job.chunks_indexed = len(points)
        job.finished_at = dt.datetime.utcnow()
        document.status = "indexed"
        db.commit()
        logger.info("Indexed %s chunks for document %s", len(points), document_id)

    except Exception as exc:
        logger.exception("Ingestion failed for document %s", document_id)
        db.rollback()
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        job.error_message = str(exc)
        if job.attempt >= job.max_attempts:
            job.status = "failed"
            document = db.query(Document).filter(Document.id == document_id).first()
            document.status = "failed"
            db.commit()
        else:
            job.status = "queued"
            db.commit()
            raise self.retry(exc=exc)
    finally:
        db.close()
