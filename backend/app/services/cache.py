"""
Thin Redis wrapper used to cache fraud-prediction results and trending
analytics queries, keyed by a hash of the job text / query params.
"""
import hashlib
import json

import redis

from app.core.config import settings

_redis_client: redis.Redis | None = None


def get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def make_cache_key(prefix: str, text: str) -> str:
    digest = hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()
    return f"{prefix}:{digest}"


def cache_get(key: str) -> dict | None:
    try:
        raw = get_redis().get(key)
        return json.loads(raw) if raw else None
    except redis.RedisError:
        # Cache is a performance optimization, not a hard dependency —
        # fail open so the app still works if Redis is momentarily down.
        return None


def cache_set(key: str, value: dict, ttl: int = settings.PREDICTION_CACHE_TTL_SECONDS) -> None:
    try:
        get_redis().setex(key, ttl, json.dumps(value, default=str))
    except redis.RedisError:
        pass
