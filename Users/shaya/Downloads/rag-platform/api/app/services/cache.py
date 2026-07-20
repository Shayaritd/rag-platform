"""Query-level response cache to cut down repeat Gemini/Llama calls for
identical (project, question) pairs — the single biggest cost lever."""
import hashlib
import json
import redis

from app.core.config import get_settings

settings = get_settings()
_redis = redis.from_url(settings.REDIS_URL, decode_responses=True)


def _key(project_id: str, question: str) -> str:
    digest = hashlib.sha256(question.strip().lower().encode()).hexdigest()
    return f"querycache:{project_id}:{digest}"


def get_cached(project_id: str, question: str) -> dict | None:
    raw = _redis.get(_key(project_id, question))
    return json.loads(raw) if raw else None


def set_cached(project_id: str, question: str, response: dict) -> None:
    _redis.setex(_key(project_id, question), settings.QUERY_CACHE_TTL_SECONDS, json.dumps(response, default=str))
