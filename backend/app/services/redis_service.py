from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from app.core.config import settings

log = logging.getLogger(__name__)

_redis_client = None
_client_lock = threading.Lock()
_memory_cache: dict[str, tuple[float, Any]] = {}
_memory_cache_lock = threading.Lock()


def get_redis_client():
    """Lazily initialize and return the Redis client, or None if unavailable."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    with _client_lock:
        if _redis_client is not None:
            return _redis_client
        if not settings.REDIS_URL:
            return None
        try:
            import redis
            client = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_timeout=1.5,
                socket_connect_timeout=1.5,
            )
            client.ping()
            _redis_client = client
            log.info("Successfully connected to Redis at %s", settings.REDIS_URL)
            return _redis_client
        except Exception as exc:
            log.warning("Redis is unavailable at %s (%s). Falling back to in-memory cache.", settings.REDIS_URL, exc)
            return None


def is_redis_healthy() -> bool:
    try:
        client = get_redis_client()
        if client is not None:
            return bool(client.ping())
    except Exception:
        pass
    return False


def cache_get(key: str) -> Any | None:
    """Retrieve JSON-deserialized value from Redis or fallback in-memory cache."""
    client = get_redis_client()
    if client is not None:
        try:
            val = client.get(key)
            if val is not None:
                return json.loads(val)
        except Exception as exc:
            log.debug("Redis cache_get failed for key %s: %s", key, exc)

    # Fallback to in-memory cache
    with _memory_cache_lock:
        entry = _memory_cache.get(key)
        if entry is not None:
            expires_at, val = entry
            if time.time() < expires_at:
                return val
            else:
                _memory_cache.pop(key, None)
    return None


def cache_set(key: str, value: Any, ttl_seconds: int = 300) -> bool:
    """Serialize and store a JSON value in Redis or in-memory cache with TTL."""
    client = get_redis_client()
    if client is not None:
        try:
            serialized = json.dumps(value, default=str)
            client.setex(key, ttl_seconds, serialized)
            return True
        except Exception as exc:
            log.debug("Redis cache_set failed for key %s: %s", key, exc)

    with _memory_cache_lock:
        _memory_cache[key] = (time.time() + ttl_seconds, value)
    return True


def cache_delete(key: str) -> bool:
    """Delete a key from Redis and in-memory cache."""
    deleted = False
    client = get_redis_client()
    if client is not None:
        try:
            client.delete(key)
            deleted = True
        except Exception as exc:
            log.debug("Redis cache_delete failed for key %s: %s", key, exc)

    with _memory_cache_lock:
        if key in _memory_cache:
            _memory_cache.pop(key, None)
            deleted = True
    return deleted


def cache_delete_pattern(pattern: str) -> int:
    """Invalidate all keys matching pattern (e.g. 'analytics:*')."""
    count = 0
    client = get_redis_client()
    if client is not None:
        try:
            keys = client.keys(pattern)
            if keys:
                count = client.delete(*keys)
        except Exception as exc:
            log.debug("Redis cache_delete_pattern failed for %s: %s", pattern, exc)

    # In-memory pattern matching
    prefix = pattern.rstrip("*")
    with _memory_cache_lock:
        to_del = [k for k in _memory_cache if k.startswith(prefix)]
        for k in to_del:
            _memory_cache.pop(k, None)
            count += 1
    return count
