from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import CurrentUser, get_current_user
from app.db.session import get_db
from app.models import Document, Project
from app.schemas.query import QueryRequest, QueryResponse, SourceChunk
from app.services.provider_router import generate
from app.services.retrieval import hybrid_search

router = APIRouter(prefix="/api/v1/search", tags=["search"])


@router.post("", response_model=QueryResponse)
def search_documents(
    payload: QueryRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> QueryResponse:
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Question is required")

    project = db.query(Project).filter(Project.tenant_id == user.tenant_id).order_by(Project.created_at.asc()).first()
    if not project:
        raise HTTPException(status_code=404, detail="No workspace projects found")

    hits = hybrid_search(project.qdrant_collection, payload.question, payload.top_k, payload.filters)
    context = "\n\n".join(f"[{i + 1}] {h['payload']['text']}" for i, h in enumerate(hits))
    result = generate(f"Use the context below to answer the question.\n\nContext:\n{context}\n\nQuestion: {payload.question}")

    sources = [
        SourceChunk(
            document_id=h["payload"]["document_id"],
            chunk_id=str(h["id"]),
            text=h["payload"]["text"][:500],
            score=h["score"],
            page=h["payload"].get("page"),
        )
        for h in hits
    ]

    return QueryResponse(answer=result.text, sources=sources, provider_used=result.provider, latency_ms=0, cache_hit=False)


@router.post("/chat", response_model=QueryResponse)
def chat_with_documents(
    payload: QueryRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> QueryResponse:
    return search_documents(payload=payload, db=db, user=user)


@router.get("/suggestions")
def get_suggestions(
    q: str | None = None,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> dict[str, list[str]]:
    if not q:
        return {"suggestions": ["Summarize this document", "Find key insights", "Show me recent updates"]}

    project = db.query(Project).filter(Project.tenant_id == user.tenant_id).order_by(Project.created_at.asc()).first()
    if not project:
        return {"suggestions": []}

    documents = (
        db.query(Document)
        .join(Project, Document.project_id == Project.id)
        .filter(Project.tenant_id == user.tenant_id)
        .limit(5)
        .all()
    )
    suggestions = [f"Search {doc.filename}" for doc in documents]
    return {"suggestions": suggestions or ["Try a broader query"]}
