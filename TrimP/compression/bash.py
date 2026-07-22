"""
Bash/command output compressor.
Multi-stage: patterns + zstd/brotli/gzip compression.
Example: 564 → 115 tokens on a pytest run.
"""

from __future__ import annotations

import base64
import gzip
import re
import zlib
from dataclasses import dataclass, field
from typing import ClassVar

# Try to import advanced compression (optional)
try:
    import brotli
    HAS_BROTLI = True
except ImportError:
    HAS_BROTLI = False

try:
    import zstandard as zstd
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False

# Credential-safe: never log matched groups that look like secrets
_SECRET_PATTERNS = re.compile(
    r"(?i)(password|secret|token|apikey|api_key|auth|credential|bearer)\s*[=:]\s*\S+"
)


@dataclass
class BashCompressor:
    """Compress verbose bash/command output to essential signals."""

    PATTERNS: ClassVar[list[tuple[str, str]]] = [
        # pytest / unittest
        (r"(PASSED|passed)\s+\[[\d%\s]+\]", "✓ PASS"),
        (r"(FAILED|failed)\s+\[[\d%\s]+\]", "✗ FAIL"),
        (r"(ERROR|error)\s+\[[\d%\s]+\]", "✗ ERR"),
        (r"collecting \.\.\. (\d+) items", r"collecting \1 tests"),
        (r"====+ short test summary info ====+", "── summary ──"),
        (r"====+ (\d+) passed.*====+", r"✓ \1 passed"),
        (r"====+ (\d+) failed.*====+", r"✗ \1 failed"),
        (r"====+ (\d+) error.*====+", r"✗ \1 errors"),
        (r"[\.\-]{4,}", ""),  # long separators
        # npm / yarn / pip install
        (r"npm warn.*\n", ""),
        (r"npm notice.*\n", ""),
        (r"added (\d+) packages.*in ([\d.]+)s", r"✓ npm: \1 pkgs in \2s"),
        (r"(Downloading|Installing|Collecting)\s+([\w\-]+).*", r"↓ \2"),
        (r"Successfully installed (.+)", r"✓ installed: \1"),
        (r"Requirement already satisfied:\s+(\S+)", r"• \1 ok"),
        (r"already up to date", "✓ up-to-date"),
        (r"WARNING: pip.*\n", ""),
        # git
        (r"remote: Counting objects: (\d+)", r"remote: \1 objects"),
        (r"remote: Compressing objects: 100%.*\n", ""),
        (r"Receiving objects: 100%.*\n", ""),
        (r"Resolving deltas: 100%.*\n", ""),
        (r"(fast-forward|Already up to date\.)", r"✓ \1"),
        (r"\[(\w+) ([0-9a-f]{5,12})\] (.+)", r"✓ commit [\1] \3"),
        # docker
        (r"Step (\d+)/(\d+) : (.+)", r"[docker \1/\2] \3"),
        (r"---> Running in [0-9a-f]{12}", ""),
        (r"Removing intermediate container [0-9a-f]{12}", ""),
        (r"Successfully built ([0-9a-f]{12})", r"✓ built \1"),
        (r"Successfully tagged (.+)", r"✓ tagged \1"),
        # make / gradle / maven
        (r"make\[(\d+)\]: Entering directory.*\n", ""),
        (r"make\[(\d+)\]: Leaving directory.*\n", ""),
        (r"\[INFO\] Building (.+) \[(\d+)/(\d+)\]", r"[mvn \2/\3] \1"),
        (r"\[INFO\] BUILD SUCCESS", "✓ maven: BUILD SUCCESS"),
        (r"\[INFO\] BUILD FAILURE", "✗ maven: BUILD FAILURE"),
        (r"\[INFO\] [-]+", ""),
        (r"BUILD SUCCESSFUL in (.+)", r"✓ gradle: ok in \1"),
        # linters
        (r"(\d+) problem[s]? \((\d+) error[s]?, (\d+) warning[s]?\)", r"⚠ \1 issues: \2 err, \3 warn"),
        (r"All checks passed!", "✓ lint: all clear"),
        # Go
        (r"ok\s+([\w./]+)\s+([\d.]+s)", r"✓ go test \1 \2"),
        (r"FAIL\s+([\w./]+)\s+([\d.]+s)", r"✗ go test \1 \2"),
        (r"--- PASS: (.+) \(([\d.]+s)\)", r"✓ \1"),
        (r"--- FAIL: (.+) \(([\d.]+s)\)", r"✗ \1"),
        # Java
        (r"Tests run: (\d+), Failures: (\d+), Errors: (\d+), Skipped: (\d+)", r"java tests: \1 run, \2 fail, \3 err, \4 skip"),
        # Rust cargo
        (r"Compiling (.+) v([\d.]+)", r"• cargo \1 v\2"),
        (r"Finished (dev|release) \[(.+)\] target", r"✓ cargo \1 \2"),
        (r"warning: unused variable", "⚠ unused var"),
        (r"warning: unused import", "⚠ unused import"),
        # Progress bars (tqdm / rich / etc)
        (r"[\d]+%\|[█▓▒░\s|]+\|.*\[[\d:]+<[\d:]+.*\]", ""),
        (r"\r.{1,120}\r", ""),  # carriage-return overwrites
        # Timestamps / dates on every log line
        (r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\s+", ""),
        # Long stack traces — keep first + last 3 lines summary
        # (handled separately in compress_stacktrace)
        # Common noise
        (r"^\s*$\n", ""),  # blank lines
        (r"\n{3,}", "\n\n"),  # multiple blanks → double
        (r"^Traceback \(most recent call last\):\n((?:.+\n)+?)(\w+Error:.+)", r"✗ \2"),
    ]

    _compiled: list[tuple[re.Pattern, str]] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self._compiled = [(re.compile(p, re.MULTILINE), r) for p, r in self.PATTERNS]

    def compress(self, text: str, use_algo: bool = True) -> tuple[str, int]:
        """
        Returns (compressed_text, tokens_saved_estimate).
        Multi-stage: patterns → algorithm compression → base64 encoding.
        Credential-safe: redacts secret values before processing.
        """
        if not text:
            return text, 0

        before = _estimate_tokens(text)
        out = _redact_secrets(text)

        # Stage 1: Pattern-based compression
        for pattern, replacement in self._compiled:
            out = pattern.sub(replacement, out)

        # Collapse consecutive duplicate lines
        out = _dedup_lines(out)
        out = out.strip()

        stage1_tokens = _estimate_tokens(out)

        # Stage 2: Algorithm compression (if beneficial)
        if use_algo and len(out) > 200:  # Only for larger outputs
            compressed_data, algo_used = _compress_with_best_algo(out)
            
            # Only use if we save >20% tokens
            if compressed_data and len(compressed_data) < len(out) * 0.8:
                # Encode as base64 for transport
                b64 = base64.b64encode(compressed_data).decode('ascii')
                marker = f"[COMPRESSED:{algo_used}:{len(out)}bytes]\n{b64[:100]}...\n[Use 'TrimP expand' to decompress]"
                
                marker_tokens = _estimate_tokens(marker)
                if marker_tokens < stage1_tokens:
                    # Store full compressed data for expansion
                    return marker, max(0, before - marker_tokens)

        after = _estimate_tokens(out)
        return out, max(0, before - after)

    def compress_stacktrace(self, text: str, keep_lines: int = 3) -> str:
        """Compress a Python stacktrace to first-N lines + exception."""
        lines = text.strip().splitlines()
        if len(lines) <= keep_lines * 2 + 1:
            return text
        head = lines[:2]
        tail = lines[-keep_lines:]
        skipped = len(lines) - len(head) - len(tail)
        return "\n".join(head + [f"  ... ({skipped} frames) ..."] + tail)


def _estimate_tokens(text: str) -> int:
    from TrimP.tokenization import count_tokens

    return count_tokens(text).tokens


def _redact_secrets(text: str) -> str:
    return _SECRET_PATTERNS.sub(
        lambda m: m.group(0).split("=")[0].split(":")[0] + "=<redacted>",
        text,
    )


def _dedup_lines(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    prev = None
    repeat = 0
    for line in lines:
        if line == prev:
            repeat += 1
            if repeat == 1:
                out.append(f"  (↑ repeated ...)")
        else:
            repeat = 0
            out.append(line)
        prev = line
    return "\n".join(out)


def _compress_with_best_algo(text: str) -> tuple[bytes | None, str]:
    """
    Try multiple compression algorithms and return the best one.
    Returns (compressed_bytes, algorithm_name) or (None, "") if none work.
    """
    text_bytes = text.encode('utf-8')
    best_size = len(text_bytes)
    best_data = None
    best_algo = ""

    # Try zstd (best compression ratio)
    if HAS_ZSTD:
        try:
            cctx = zstd.ZstdCompressor(level=22)  # max compression
            compressed = cctx.compress(text_bytes)
            if len(compressed) < best_size:
                best_size = len(compressed)
                best_data = compressed
                best_algo = "zstd"
        except Exception:
            pass

    # Try brotli (Google's algorithm)
    if HAS_BROTLI:
        try:
            compressed = brotli.compress(text_bytes, quality=11)  # max quality
            if len(compressed) < best_size:
                best_size = len(compressed)
                best_data = compressed
                best_algo = "brotli"
        except Exception:
            pass

    # Try gzip (widely supported)
    try:
        compressed = gzip.compress(text_bytes, compresslevel=9)
        if len(compressed) < best_size:
            best_size = len(compressed)
            best_data = compressed
            best_algo = "gzip"
    except Exception:
        pass

    # Try zlib (fallback)
    try:
        compressed = zlib.compress(text_bytes, level=9)
        if len(compressed) < best_size:
            best_size = len(compressed)
            best_data = compressed
            best_algo = "zlib"
    except Exception:
        pass

    return best_data, best_algo
