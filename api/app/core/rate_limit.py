"""
Simple Redis-backed sliding-window rate limiter and per-project daily quota check.
Deliberately lightweight (no external limiter library) since a fixed-window
counter with TTL is enough at this scale and keeps the dependency surface small.
"""
import redis
from fastapi import HTTPException, Request

from app.core.config import get_settings

settings = get_settings()
_redis = redis.from_url(settings.REDIS_URL, decode_responses=True)


def check_rate_limit(request: Request, identity: str) -> None:
    key = f"ratelimit:{identity}:{request.url.path}"
    current = _redis.incr(key)
    if current == 1:
        _redis.expire(key, 60)
    if current > settings.RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Rate limit exceeded, slow down")


def check_daily_quota(project_id: str, limit: int) -> None:
    key = f"quota:{project_id}:daily"
    current = _redis.incr(key)
    if current == 1:
        _redis.expire(key, 86400)
    if current > limit:
        raise HTTPException(status_code=429, detail="Daily query quota exceeded for this project")
