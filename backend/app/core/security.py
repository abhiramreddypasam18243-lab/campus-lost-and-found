import hashlib
import secrets
import time
from datetime import UTC, datetime

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, Request, status

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


def check_tls_requirement(request: Request) -> None:
    """SEC7 & AC-07: Reject logins over plain HTTP from non-localhost clients."""
    client_host = request.client.host if request.client else "127.0.0.1"
    is_localhost = client_host in ("127.0.0.1", "localhost", "::1", "testclient", "testserver")

    if not is_localhost:
        # Check scheme or forwarded proto only from trusted proxy
        scheme = request.url.scheme
        forwarded_proto = request.headers.get("X-Forwarded-Proto")

        # Untrusted clients cannot forge forwarded headers
        is_secure = scheme == "https" or (
            forwarded_proto == "https" and client_host in ("127.0.0.1", "nginx")
        )

        if not is_secure:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "tls_required",
                    "message": "Credentials require TLS over the network.",
                },
            )
