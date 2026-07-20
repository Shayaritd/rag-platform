import uuid
from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str
    top_k: int = 5
    filters: dict | None = None   # metadata filters, e.g. {"document_id": "..."}


class SourceChunk(BaseModel):
    document_id: uuid.UUID
    chunk_id: str
    text: str
    score: float
    page: int | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceChunk]
    provider_used: str
    latency_ms: int
    cache_hit: bool
