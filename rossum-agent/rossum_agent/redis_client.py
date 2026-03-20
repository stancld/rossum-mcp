"""Redis client factory for change tracking."""

from __future__ import annotations

import logging
import os

import redis

logger = logging.getLogger(__name__)


class RedisConnection:
    """Minimal Redis connection wrapper for change tracking (commits, snapshots)."""

    def __init__(self, host: str | None = None, port: int | None = None) -> None:
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port if port is not None else int(os.getenv("REDIS_PORT", "6379"))
        self._client: redis.Redis | None = None

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis(
                host=self.host, port=self.port, decode_responses=False, socket_connect_timeout=5
            )
        return self._client

    def is_connected(self) -> bool:
        try:
            self.client.ping()
            return True
        except Exception:
            return False

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None
