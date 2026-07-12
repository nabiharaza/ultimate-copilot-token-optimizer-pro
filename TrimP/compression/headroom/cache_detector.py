"""Cache alignment detector (adapted from Headroom SDK).

Detects volatile/dynamic content that breaks Claude's prompt caching:
- UUIDs
- ISO 8601 timestamps
- JWTs
- Hex hashes (MD5/SHA1/SHA256)

Pure detection, zero dependencies, no regex.

Original: headroom/transforms/cache_aligner.py
Adapted for TrimP compression use cases.
"""

import base64
import binascii
import uuid as _uuid
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional


# Length profiles for hex hash detection
_HEX_HASH_LENGTHS = frozenset({32, 40, 64})  # MD5, SHA1, SHA256
_UUID_CANONICAL_LEN = 36
_JWT_SEGMENT_COUNT = 3
_JWT_MIN_SEGMENT_BYTES = 4

# Token classification labels
_LABEL_UUID = "uuid"
_LABEL_ISO8601 = "iso8601"
_LABEL_JWT = "jwt"
_LABEL_HEX_HASH = "hex_hash"


@dataclass(frozen=True)
class VolatileFinding:
    """One detected piece of volatile content."""

    label: str
    sample: str  # Truncated, never full content


def _is_uuid(token: str) -> bool:
    """Return True if token parses as canonical UUID.

    Accepts only 36-char form with dashes (xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx).
    """
    if len(token) != _UUID_CANONICAL_LEN:
        return False
    if token.count("-") != 4:
        return False
    try:
        _uuid.UUID(token)
    except (ValueError, AttributeError):
        return False
    return True


def _is_iso8601(token: str) -> bool:
    """Return True if token parses as ISO 8601 datetime."""
    if len(token) < 8:
        return False
    if "T" not in token and "-" not in token:
        return False
    candidate = token[:-1] + "+00:00" if token.endswith("Z") else token
    try:
        datetime.fromisoformat(candidate)
    except (ValueError, TypeError):
        return False
    return True


def _is_jwt_shape(token: str) -> bool:
    """Return True if token has shape of a JWT.

    JWT is three base64url-encoded segments separated by '.'.
    Verify shape only, not signature.
    """
    if token.count(".") != _JWT_SEGMENT_COUNT - 1:
        return False
    segments = token.split(".")
    if len(segments) != _JWT_SEGMENT_COUNT:
        return False
    for seg in segments:
        if len(seg) < _JWT_MIN_SEGMENT_BYTES:
            return False
        # base64url decode requires padding to multiple of 4
        padded = seg + "=" * (-len(seg) % 4)
        try:
            base64.urlsafe_b64decode(padded.encode("ascii"))
        except (binascii.Error, ValueError, UnicodeEncodeError):
            return False
    return True


def _is_hex_hash(token: str) -> bool:
    """Return True if token looks like MD5/SHA1/SHA256 hex digest."""
    if len(token) not in _HEX_HASH_LENGTHS:
        return False
    try:
        int(token, 16)
    except ValueError:
        return False
    return True


def _classify_token(token: str) -> Optional[str]:
    """Return label for token if it matches a volatile pattern.

    Order matters: more specific checks first.
    """
    if _is_uuid(token):
        return _LABEL_UUID
    if "." in token and _is_jwt_shape(token):
        return _LABEL_JWT
    if _is_iso8601(token):
        return _LABEL_ISO8601
    if _is_hex_hash(token):
        return _LABEL_HEX_HASH
    return None


def _split_tokens(content: str) -> List[str]:
    """Split content into whitespace-delimited tokens for inspection.

    No regex. str.split() handles all standard whitespace.
    Strip surrounding punctuation.
    """
    if not content:
        return []
    tokens: List[str] = []
    for raw in content.split():
        cleaned = raw.strip(".,;:!?\"'()[]{}<>")
        if cleaned:
            tokens.append(cleaned)
    return tokens


def detect_volatile_content(content: str) -> List[VolatileFinding]:
    """Detect volatile/dynamic content in arbitrary text.

    Pure detection: no regex, no mutation. Returns one finding per token
    that matches any structural pattern.

    Args:
        content: Text to analyze.

    Returns:
        List of VolatileFinding objects.
    """
    if not content:
        return []
    findings: List[VolatileFinding] = []
    for token in _split_tokens(content):
        label = _classify_token(token)
        if label is None:
            continue
        # Truncate sample to never log full secrets
        sample = token if len(token) <= 16 else token[:8] + "..." + token[-4:]
        findings.append(VolatileFinding(label=label, sample=sample))
    return findings


def get_cache_alignment_score(content: str) -> float:
    """Compute cache alignment score (0-100).

    Higher score means fewer detected volatile patterns.
    Penalty is flat 10 points per finding.

    Args:
        content: Text to analyze.

    Returns:
        Score from 0-100.
    """
    findings = detect_volatile_content(content)
    score = 100.0 - len(findings) * 10
    return max(0.0, min(100.0, score))
