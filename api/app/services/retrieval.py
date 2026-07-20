"""
Hybrid retrieval: merge dense (semantic) and keyword (lexical) hits with a
simple weighted score, then hand the top chunks to a reranker hook.
Reranking is stubbed as a no-op sort by default; swap in a cross-encoder
(e.g. bge-reranker) later without touching callers.
"""
from app.services import vector_store
from app.services.embeddings import get_embedder


def hybrid_search(collection: str, query: str, top_k: int, filters: dict | None = None) -> list[dict]:
    embedder = get_embedder()
    query_vector = embedder.embed([query])[0]

    dense_hits = vector_store.dense_search(collection, query_vector, top_k=top_k * 2, filters=filters)
    keyword_hits = vector_store.keyword_search(collection, query, top_k=top_k * 2, filters=filters)

    merged: dict[str, dict] = {}
    for hit in dense_hits:
        merged[str(hit.id)] = {"id": hit.id, "payload": hit.payload, "score": hit.score * 0.7}
    for hit in keyword_hits:
        key = str(hit.id)
        bonus = 0.3
        if key in merged:
            merged[key]["score"] += bonus
        else:
            merged[key] = {"id": hit.id, "payload": hit.payload, "score": bonus}

    ranked = sorted(merged.values(), key=lambda x: x["score"], reverse=True)
    return rerank(ranked)[:top_k]


def rerank(candidates: list[dict]) -> list[dict]:
    """Hook for a real cross-encoder reranker. No-op today: candidates are
    already sorted by hybrid score."""
    return candidates
