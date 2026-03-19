import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


class EmailRateLimiter:
    """In-memory sliding window rate limiter keyed by string (e.g. email).

    Suitable for single-instance deployments (e.g. Cloud Run with max_instances=1). For
    multi-instance scaling, replace with a shared store like Redis.
    """

    def __init__(self, max_requests: int, window_seconds: int):
        """Initialize the rate limiter.

        Parameters
        ----------
        max_requests : int
            Maximum number of allowed requests within the time window.
        window_seconds : int
            Time window in seconds for rate limiting.
        """
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict[str, list[float]] = defaultdict(list)

    def check(self, key: str) -> bool:
        """Check if a request is allowed for the given key.

        Returns True if allowed, False if rate limit exceeded. Cleans up stale
        timestamps on each call.
        """
        now = time.monotonic()
        cutoff = now - self.window_seconds

        # Prune expired timestamps for this key
        timestamps = self._requests[key]
        self._requests[key] = [t for t in timestamps if t > cutoff]

        if len(self._requests[key]) >= self.max_requests:
            return False

        self._requests[key].append(now)
        return True
