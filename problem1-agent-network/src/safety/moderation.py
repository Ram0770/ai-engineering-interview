"""Content moderation, rate limiting, and community abuse reporting."""

import time
from collections import defaultdict

# In-memory sliding window rate limiter: agent_id -> list of timestamps
_rate_limit_records: dict[str, list[float]] = defaultdict(list)

# Prohibited harassment / abuse keywords
PROHIBITED_TERMS = [
    "hate_speech",
    "phishing_scam",
    "malware_distribute",
    "stolen_credentials",
    "lottery",
    "crypto_scam",
    "free money",
]


class RateLimitExceededError(Exception):
    """Raised when an agent exceeds publishing frequency limits."""

    pass


class ModerationViolationError(Exception):
    """Raised when content violates safety policies."""

    pass


def check_rate_limit(agent_id: str, max_requests_per_minute: int = 30) -> None:
    """Enforces sliding window rate limits per agent."""
    now = time.time()
    window_start = now - 60.0

    timestamps = _rate_limit_records[agent_id]
    # Prune timestamps older than 60 seconds
    valid_timestamps = [t for t in timestamps if t > window_start]
    _rate_limit_records[agent_id] = valid_timestamps

    if len(valid_timestamps) >= max_requests_per_minute:
        raise RateLimitExceededError(
            f"Rate limit exceeded: max {max_requests_per_minute} publications per minute."
        )

    _rate_limit_records[agent_id].append(now)


def moderate_content(title: str, content: str) -> tuple[bool, str]:
    """Inspects text for abuse, prohibited content, or illegal material."""
    combined = (title + " " + content).lower()
    for term in PROHIBITED_TERMS:
        if term in combined:
            return False, f"Content violates safety guidelines: contains prohibited term '{term}'."

    return True, "Approved"
