"""Deprecated compatibility shim for unsafe stop-word deletion.

Words such as ``just``, ``really``, and modal phrases can carry user intent.
TrimPy no longer removes them generically. Callers keep the old API while the
input is returned byte-for-byte unchanged.
"""

from __future__ import annotations


class StopWordRemover:
    def __init__(self, aggressive: bool = False):
        self.aggressive = aggressive

    def compress(self, text: str) -> tuple[str, int]:
        return text, 0
