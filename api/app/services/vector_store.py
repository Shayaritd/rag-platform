"""
Thin abstraction over Qdrant so the retrieval layer never talks to the
client library directly. Swapping in Pinecone later means implementing
this same interface, not touching callers.
"""
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.core.config import get_settings

settings = get_settings()
_client = QdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY)


def collection_name(tenant_id: str, project_id: str) -> str:
    return f"{settings.QDRANT_COLLECTION_PREFIX}_{tenant_id}_{project_id}"


def ensure_collection(name: str) -> None:
    existing = [c.name for c in _client.get_collections().collections]
    if name not in existing:
        _client.create_collection(
            collection_name=name,
            vectors_config=qmodels.VectorParams(size=settings.EMBEDDING_DIM, distance=qmodels.Distance.COSINE),
        )


def upsert_chunks(collection: str, points: list[dict]) -> None:
    """points: [{id, vector, payload: {text, document_id, page, keywords}}]"""
    ensure_collection(collection)
    _client.upsert(
        collection_name=collection,
        points=[
            qmodels.PointStruct(id=p["id"], vector=p["vector"], payload=p["payload"])
            for p in points
        ],
    )


def dense_search(collection: str, query_vector: list[float], top_k: int, filters: dict | None = None):
    qfilter = None
    if filters:
        qfilter = qmodels.Filter(
            must=[qmodels.FieldCondition(key=k, match=qmodels.MatchValue(value=v)) for k, v in filters.items()]
        )
    return _client.search(collection_name=collection, query_vector=query_vector, limit=top_k, query_filter=qfilter)


def keyword_search(collection: str, query_text: str, top_k: int, filters: dict | None = None):
    """Qdrant full-text match on the payload 'text' field (requires a text index on that field).
    Combined with dense_search results for hybrid retrieval."""
    must = [qmodels.FieldCondition(key="text", match=qmodels.MatchText(text=query_text))]
    if filters:
        must += [qmodels.FieldCondition(key=k, match=qmodels.MatchValue(value=v)) for k, v in filters.items()]
    return _client.scroll(
        collection_name=collection,
        scroll_filter=qmodels.Filter(must=must),
        limit=top_k,
    )[0]
