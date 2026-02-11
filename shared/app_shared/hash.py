"""
HMAC-based hashing for identifiers in traces (no raw IDs/emails).
"""
import hashlib
import hmac
import os


def hash_id(value: str, secret: str | None = None) -> str:
    """Return a short HMAC-SHA256 hash of value for use in span attributes. No raw IDs."""
    if not value or not value.strip():
        return ""
    key = (secret or os.environ.get("TRACE_ID_HASH_SECRET") or "default-change-me").encode("utf-8")
    raw = value.strip().encode("utf-8")
    digest = hmac.new(key, raw, hashlib.sha256).hexdigest()
    return digest[:16]
