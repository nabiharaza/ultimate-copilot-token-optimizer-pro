"""
JSON/tabular output compressor.
Value-preserving columnar format.
"""

from __future__ import annotations

import json
import re
from typing import Any


class JsonTableCompressor:
    """Compress JSON arrays and tabular CLI output."""

    def compress_json(self, text: str, max_rows: int = 20, max_depth: int = 2) -> tuple[str, int]:
        before = _est(text)
        try:
            data = json.loads(text.strip())
        except (json.JSONDecodeError, ValueError):
            return text, 0

        out = _render(data, max_rows, max_depth)
        if out is None:
            return text, 0

        after = _est(out)
        return out, max(0, before - after)

    def compress_table(self, text: str, max_rows: int = 30) -> tuple[str, int]:
        """Compress wide table output (jq, kubectl, psql, etc)."""
        before = _est(text)
        lines = [l for l in text.strip().splitlines() if l.strip()]
        if len(lines) <= max_rows + 2:
            return text, 0

        # Keep header rows (first 2) + top max_rows data rows
        headers = lines[:2]
        data = lines[2:max_rows + 2]
        omitted = len(lines) - 2 - len(data)
        out = "\n".join(headers + data)
        if omitted > 0:
            out += f"\n... {omitted} more rows"

        return out, max(0, before - _est(out))

    def compress_key_value(self, text: str) -> tuple[str, int]:
        """Compress key=value or key: value output, deduplicating repeated keys."""
        before = _est(text)
        seen: dict[str, str] = {}
        lines = text.strip().splitlines()

        for line in lines:
            m = re.match(r"^\s*([\w.\-/]+)\s*[:=]\s*(.+)", line)
            if m:
                seen[m.group(1)] = m.group(2).strip()

        if len(seen) >= len(lines) * 0.8:
            return text, 0

        out = "\n".join(f"{k}: {v}" for k, v in seen.items())
        return out, max(0, before - _est(out))


def _render(data: Any, max_rows: int, max_depth: int, depth: int = 0) -> str | None:
    if depth > max_depth:
        return str(data)[:80]

    if isinstance(data, list):
        if not data:
            return "[]"
        if len(data) > max_rows:
            omitted = len(data) - max_rows
            data = data[:max_rows]
            suffix = f"\n... {omitted} more items"
        else:
            suffix = ""

        if data and isinstance(data[0], dict):
            return _render_table(data) + suffix

        lines = [json.dumps(item, default=str) for item in data]
        return "\n".join(lines) + suffix

    if isinstance(data, dict):
        if len(data) > max_rows:
            items = list(data.items())[:max_rows]
            omitted = len(data) - max_rows
            out = json.dumps(dict(items), indent=2, default=str)
            return out + f"\n... {omitted} more keys"
        return json.dumps(data, indent=2, default=str)

    return json.dumps(data, default=str)


def _render_table(rows: list[dict]) -> str:
    if not rows:
        return ""
    all_keys: list[str] = []
    seen_keys: set[str] = set()
    for row in rows:
        for k in row:
            if k not in seen_keys:
                all_keys.append(k)
                seen_keys.add(k)

    col_widths = {k: max(len(str(k)), max(len(str(row.get(k, "")))[:30] for row in rows)) for k in all_keys}
    header = " | ".join(str(k).ljust(col_widths[k]) for k in all_keys)
    sep = "-+-".join("-" * col_widths[k] for k in all_keys)
    data_rows = [
        " | ".join(str(row.get(k, ""))[:30].ljust(col_widths[k]) for k in all_keys)
        for row in rows
    ]
    return "\n".join([header, sep] + data_rows)


def _est(t: str) -> int:
    from TrimP.tokenization import count_tokens

    return count_tokens(t).tokens
