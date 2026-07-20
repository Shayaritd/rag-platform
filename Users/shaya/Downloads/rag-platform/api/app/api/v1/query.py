import time
from fastapi import APIRouter, Depends, Request, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Project, QueryLog
from app.schemas.query import QueryRequest, QueryResponse, SourceChunk
from app.core.security import get_current_user, CurrentUser
from app.core.rate_limit import check_rate_limit, check_daily_quota
from app.services.retrieval import hybrid_search
from app.services.provider_router import generate
from app.services import cache

router = APIRouter(prefix="/projects/{project_id}/query", tags=["query"])

PROMPT_TEMPLATE = """Answer the question using ONLY the context below. Cite sources as [n].
If the answer isn't in the context, say you don't know.

Context:
{context}

Question: {question}
Answer:"""


@router.post("", response_model=QueryResponse)
def query_project(
    project_id: str,
    payload: QueryRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    check_rate_limit(request, identity=user.user_id)
    project = db.query(Project).filter(Project.id == project_id, Project.tenant_id == user.tenant_id).first()
    check_daily_quota(project_id, project.daily_query_quota)

    cached = cache.get_cached(project_id, payload.question)
    if cached:
        return QueryResponse(**cached, cache_hit=True)

    start = time.perf_counter()
    hits = hybrid_search(project.qdrant_collection, payload.question, payload.top_k, payload.filters)

    context = "\n\n".join(f"[{i+1}] {h['payload']['text']}" for i, h in enumerate(hits))
    prompt = PROMPT_TEMPLATE.format(context=context, question=payload.question)
    try:
        result = generate(prompt)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"LLM generation failed: {str(exc)}. Please set GEMINI_API_KEY in .env or wait for Ollama model download."
        )
    latency_ms = int((time.perf_counter() - start) * 1000)

    sources = [
        SourceChunk(document_id=h["payload"]["document_id"], chunk_id=str(h["id"]),
                    text=h["payload"]["text"][:500], score=h["score"], page=h["payload"].get("page"))
        for h in hits
    ]

    db.add(QueryLog(
        project_id=project_id, user_id=user.user_id, question=payload.question,
        provider_used=result.provider, latency_ms=latency_ms,
        prompt_tokens_est=len(prompt.split()), completion_tokens_est=len(result.text.split()),
    ))
    db.commit()

    response = {"answer": result.text, "sources": [s.model_dump(mode="json") for s in sources],
                "provider_used": result.provider, "latency_ms": latency_ms}
    cache.set_cached(project_id, payload.question, response)

    return QueryResponse(**response, cache_hit=False)
