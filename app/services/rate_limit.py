import math
import time
from collections import deque
from collections.abc import Callable


class LoginRateLimiter:
    """In-memory sliding-window limit on failed logins per key (username or client IP).

    State lives in the process, which fits the single-worker deployment. Behind a
    reverse proxy without forwarded headers every client shares the proxy's IP.
    """

    DEFAULT_MAX_FAILURES = 5
    DEFAULT_WINDOW_SECONDS = 300
    MAX_TRACKED_KEYS = 10_000

    def __init__(
        self,
        max_failures: int = DEFAULT_MAX_FAILURES,
        window_seconds: int = DEFAULT_WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self._clock = clock
        self._failures: dict[str, deque[float]] = {}

    def _prune(self, key: str, now: float) -> deque[float] | None:
        attempts = self._failures.get(key)
        if attempts is None:
            return None
        while attempts and attempts[0] <= now - self.window_seconds:
            attempts.popleft()
        if not attempts:
            del self._failures[key]
            return None
        return attempts

    def retry_after(self, key: str) -> int:
        """Seconds until the next attempt is allowed; 0 if not blocked."""
        now = self._clock()
        attempts = self._prune(key, now)
        if attempts is None or len(attempts) < self.max_failures:
            return 0
        return max(1, math.ceil(attempts[0] + self.window_seconds - now))

    def record_failure(self, key: str) -> None:
        now = self._clock()
        if len(self._failures) >= self.MAX_TRACKED_KEYS:
            for tracked in list(self._failures):
                self._prune(tracked, now)
        self._failures.setdefault(key, deque()).append(now)

    def record_success(self, key: str) -> None:
        self._failures.pop(key, None)

    def reset(self) -> None:
        self._failures.clear()
