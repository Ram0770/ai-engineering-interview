"""Signed HMAC webhook generation and SSRF protection."""

import hashlib
import hmac
import ipaddress
import socket
import time
from urllib.parse import urlparse


class SSRFSecurityViolationError(ValueError):
    """Raised when a target webhook URL resolves to a forbidden private or loopback IP."""

    pass


def is_safe_webhook_url(url: str, allow_localhost: bool = False) -> tuple[bool, str]:
    """Validates URL schemes and resolves target IPs to prevent SSRF and DNS rebinding attacks.

    Blocks:
    - RFC 1918 Private Ranges (10.0.0.0/8, 172.16.0.0/12, 192.168.0.0/16)
    - Loopback Addresses (127.0.0.0/8, ::1)
    - Link-Local & Cloud Metadata (169.254.0.0/16, 169.254.169.254, fe80::/10)
    - Forbidden Schemes (file://, gopher://, ftp://)
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False, "Malformed URL format"

    # Scheme validation: Only HTTPS permitted in production; HTTP allowed if allow_localhost=True
    if allow_localhost:
        if parsed.scheme not in ("http", "https"):
            return False, f"Unsupported URL scheme: {parsed.scheme}"
    else:
        if parsed.scheme != "https":
            return False, "Production webhooks must strictly use HTTPS"

    hostname = parsed.hostname
    if not hostname:
        return False, "Missing hostname in webhook URL"

    if allow_localhost and (hostname == "localhost" or hostname == "127.0.0.1"):
        return True, "Localhost allowed for development/testing"

    # Resolve IP address to detect private / internal network targets
    try:
        addr_info = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False, f"Could not resolve host: {hostname}"

    for item in addr_info:
        ip_str = item[4][0]
        ip = ipaddress.ip_address(ip_str)

        if ip.is_loopback:
            return False, f"SSRF blocked: target resolves to loopback IP {ip_str}"
        if ip.is_private and not allow_localhost:
            return False, f"SSRF blocked: target resolves to RFC 1918 private IP {ip_str}"
        if ip.is_link_local:
            return False, f"SSRF blocked: target resolves to link-local IP {ip_str}"
        if str(ip) == "169.254.169.254":
            return False, "SSRF blocked: target resolves to cloud instance metadata endpoint"

    return True, "Safe"


def generate_webhook_signature(
    payload_json: str,
    signing_secret: str,
    timestamp: int | None = None,
) -> str:
    """Computes an HMAC-SHA256 signature header with timestamp replay protection.

    Format: 't=1731500000,v1=9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08'
    """
    ts = timestamp if timestamp is not None else int(time.time())
    signed_payload = f"t={ts}.{payload_json}"

    sig = hmac.new(
        signing_secret.encode("utf-8"),
        signed_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()

    return f"t={ts},v1={sig}"


def verify_webhook_signature(
    payload_json: str,
    signature_header: str,
    signing_secret: str,
    max_drift_seconds: int = 300,
) -> bool:
    """Validates an incoming webhook signature and checks timestamp freshness."""
    if not signature_header or "t=" not in signature_header or "v1=" not in signature_header:
        return False

    parts: dict[str, str] = {}
    for item in signature_header.split(","):
        if "=" in item:
            k, v = item.split("=", 1)
            parts[k.strip()] = v.strip()

    ts_str = parts.get("t")
    v1_sig = parts.get("v1")

    if not ts_str or not v1_sig:
        return False

    try:
        timestamp = int(ts_str)
    except ValueError:
        return False

    # Check replay window (reject if older than max_drift_seconds)
    current_time = int(time.time())
    if abs(current_time - timestamp) > max_drift_seconds:
        return False

    expected_header = generate_webhook_signature(payload_json, signing_secret, timestamp=timestamp)
    expected_sig = expected_header.split("v1=")[1]

    return hmac.compare_digest(v1_sig, expected_sig)
