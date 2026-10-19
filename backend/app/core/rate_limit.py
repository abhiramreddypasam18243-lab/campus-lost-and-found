import time


class BrowseRateLimiter:
    """In-memory sliding window rate limiter for browse endpoints (P5, AC-43).

    Limits users to max_requests within window_seconds (default 120 req / 60 sec).
    """

    def __init__(self, max_requests: int = 120, window_seconds: int = 60) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # key: user_id -> list of timestamps
        self.requests: dict[str, list[float]] = {}

    def _clean_old(self, key: str, now: float) -> list[float]:
        if key not in self.requests:
            return []
        valid = [t for t in self.requests[key] if now - t < self.window_seconds]
        if valid:
            self.requests[key] = valid
        else:
            self.requests.pop(key, None)
        return valid

    def check_and_record(self, key: str) -> tuple[bool, int]:
        """Check if request is allowed. If allowed, record timestamp and return (False, 0).

        If limit exceeded, return (True, retry_after_seconds).
        """
        now = time.time()
        valid = self._clean_old(key, now)
        if len(valid) >= self.max_requests:
            oldest = valid[0]
            retry_after = max(1, int(self.window_seconds - (now - oldest)))
            return True, retry_after

        valid.append(now)
        self.requests[key] = valid
        return False, 0

    def reset(self, key: str | None = None) -> None:
        if key is None:
            self.requests.clear()
        else:
            self.requests.pop(key, None)


browse_rate_limiter = BrowseRateLimiter(max_requests=120, window_seconds=60)
