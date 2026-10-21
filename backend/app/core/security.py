import hashlib
import secrets
import socket
import time
from datetime import UTC, datetime

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, Request, status

from app.core.config import settings

ph = PasswordHasher(
    time_cost=2,
    memory_cost=65536,
    parallelism=1,
    hash_len=32,
    salt_len=16,
)

# Precomputed dummy hash for timing protection (SEC5)
DUMMY_ARGON2ID_HASH = ph.hash("dummy_password_for_timing_protection_12345")


def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    return ph.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify password against Argon2id hash."""
    try:
        return ph.verify(hashed_password, password)
    except (VerifyMismatchError, Exception):
        return False


def verify_dummy_password() -> None:
    """Run dummy verification to prevent timing attacks when user does not exist."""
    try:
        ph.verify(DUMMY_ARGON2ID_HASH, "wrong_dummy_password")
    except Exception:
        pass


def generate_secure_token(nbytes: int = 32) -> str:
    """Generate a cryptographically secure random token."""
    return secrets.token_urlsafe(nbytes)


def hash_token(token: str) -> str:
    """Compute SHA-256 hex digest of a token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def utc_now() -> datetime:
    """Current timestamp in UTC."""
    return datetime.now(UTC)


class LoginRateLimiter:
    """In-memory rate limiter for failed login attempts (SEC6, AC-04)."""

    def __init__(self, max_attempts: int = 5, window_seconds: int = 900) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        # key: identifier -> list of failure timestamps
        self.attempts: dict[str, list[float]] = {}

    def _clean_old_attempts(self, key: str, now: float) -> list[float]:
        if key not in self.attempts:
            return []
        valid = [t for t in self.attempts[key] if now - t < self.window_seconds]
        if valid:
            self.attempts[key] = valid
        else:
            self.attempts.pop(key, None)
        return valid

    def is_rate_limited(self, key: str) -> tuple[bool, int]:
        """Check if key is rate limited. Returns (is_limited, retry_after_seconds)."""
        now = time.time()
        valid = self._clean_old_attempts(key, now)
        if len(valid) >= self.max_attempts:
            oldest = valid[0]
            retry_after = max(1, int(self.window_seconds - (now - oldest)))
            return True, retry_after
        return False, 0

    def record_failure(self, key: str) -> None:
        now = time.time()
        valid = self._clean_old_attempts(key, now)
        valid.append(now)
        self.attempts[key] = valid

    def reset(self, key: str) -> None:
        self.attempts.pop(key, None)


login_rate_limiter = LoginRateLimiter(max_attempts=5, window_seconds=900)


LOCALHOST_NAMES = ("127.0.0.1", "localhost", "::1", "testclient", "testserver")


_PROXY_CACHE_SECONDS = 30.0
_proxy_cache: tuple[float, tuple[str, ...], set[str]] | None = None


def _trusted_proxy_addresses() -> set[str]:
    """Addresses of the configured reverse proxies (SEC7).

    Hostnames are re-resolved every 30 seconds, because a container gets a new address when it
    is recreated; the short cache keeps a slow or failing DNS lookup off every request.
    """
    global _proxy_cache
    names = tuple(settings.TRUSTED_PROXIES)
    now = time.monotonic()
    if _proxy_cache and _proxy_cache[1] == names and now - _proxy_cache[0] < _PROXY_CACHE_SECONDS:
        return _proxy_cache[2]
    addresses: set[str] = set(names)
    for entry in names:
        try:
            for info in socket.getaddrinfo(entry, None):
                addresses.add(str(info[4][0]))
        except OSError:
            continue
    _proxy_cache = (now, names, addresses)
    return addresses


def request_is_tls(request: Request) -> bool:
    """True if the client's connection to us was encrypted.

    Either the request reached this process over HTTPS, or it came through a configured proxy
    that says so. Forwarded headers from any other address are ignored (AC-07).
    """
    if request.url.scheme == "https":
        return True
    client_host = request.client.host if request.client else ""
    if client_host in LOCALHOST_NAMES:
        return False
    if client_host in _trusted_proxy_addresses():
        return request.headers.get("X-Forwarded-Proto", "").lower() == "https"
    return False


def request_is_local(request: Request) -> bool:
    """True for a client on this machine.

    Directly: the socket peer is loopback. Through the proxy: its plain-HTTP listener is published
    on 127.0.0.1 only (docker-compose.yml), and it sets `X-Client-Network: loopback` itself,
    overwriting anything a client sent, so only a client on this machine can reach that listener.
    """
    client_host = request.client.host if request.client else ""
    if client_host in LOCALHOST_NAMES:
        return True
    if client_host in _trusted_proxy_addresses():
        return request.headers.get("X-Client-Network", "").lower() == "loopback"
    return False


def check_tls_requirement(request: Request) -> None:
    """SEC7 & AC-07: credentials are accepted only over TLS, or from this machine."""
    if request_is_local(request) or request_is_tls(request):
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail={
            "code": "tls_required",
            "message": "Credentials require TLS over the network.",
        },
    )
