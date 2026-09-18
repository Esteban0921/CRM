"""Limitador de intentos de login en memoria (TASK-0094).

Deliberadamente simple: este CRM es de una sola empresa y corre en un solo
proceso, asi que un diccionario en memoria es proporcionado. Si algun dia se
sirve con varios workers, el contador tiene que mudarse al Redis que ya esta
levantado (TASK-0164); hasta entonces, anadir una dependencia de cola solo para
esto seria desproporcionado (RULE-010).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field


@dataclass
class _Bucket:
    failures: list[float] = field(default_factory=list)


class LoginRateLimiter:
    def __init__(self, *, max_attempts: int, window_seconds: int) -> None:
        self._max_attempts = max_attempts
        self._window_seconds = window_seconds
        self._buckets: dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def _prune(self, bucket: _Bucket, now: float) -> None:
        cutoff = now - self._window_seconds
        bucket.failures = [stamp for stamp in bucket.failures if stamp > cutoff]

    def retry_after_seconds(self, key: str) -> int:
        """Segundos que faltan para volver a poder intentarlo, 0 si se puede."""
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None:
                return 0
            self._prune(bucket, now)
            if len(bucket.failures) < self._max_attempts:
                return 0
            oldest = min(bucket.failures)
            return max(1, int(oldest + self._window_seconds - now) + 1)

    def register_failure(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets.setdefault(key, _Bucket())
            self._prune(bucket, now)
            bucket.failures.append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._buckets.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._buckets.clear()
