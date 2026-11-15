"""Agent registration verification, challenge-response handshake, and key management."""

import hashlib
import hmac
import secrets

import httpx


def generate_api_key() -> tuple[str, str, str]:
    """Generates a raw API key, its display prefix, and its SHA-256 hash.

    Returns:
        (raw_key, prefix, key_hash)
    """
    token = secrets.token_urlsafe(32)
    raw_key = f"ak_live_{token}"
    prefix = raw_key[:12]
    key_hash = hash_token(raw_key)
    return raw_key, prefix, key_hash


def generate_signing_secret() -> str:
    """Generates a high-entropy secret for HMAC-SHA256 webhook signatures."""
    return f"whsec_{secrets.token_hex(24)}"


def hash_token(token: str) -> str:
    """Computes SHA-256 hash of an authentication token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def verify_webhook_challenge(webhook_url: str, signing_secret: str, timeout: float = 3.0) -> bool:
    """Sends a cryptographic ping challenge to the target agent webhook URL.

    The target must return HTTP 200 with JSON {"challenge": "<token>"}.
    """
    challenge_token = secrets.token_hex(16)
    payload = {"type": "verification_challenge", "challenge": challenge_token}

    # Calculate HMAC signature
    signature = hmac.new(
        signing_secret.encode("utf-8"),
        challenge_token.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "X-Agent-Challenge": challenge_token,
        "X-Agent-Signature": signature,
    }

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            res = await client.post(webhook_url, json=payload, headers=headers)
            if res.status_code == 200:
                data = res.json()
                return bool(isinstance(data, dict) and data.get("challenge") == challenge_token)
    except Exception:
        return False

    return False
