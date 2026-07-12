"""
Skeleton compressor — file structure maps.
720KB → ~250 tokens (signatures + imports only).
"""

from __future__ import annotations

import re
from pathlib import Path


class SkeletonCompressor:
    """Extract structural skeleton from source files."""

    def compress(self, content: str, file_path: str = "") -> tuple[str, int]:
        before = _est(content)
        suffix = Path(file_path).suffix.lower() if file_path else ".py"

        handlers = {
            ".py": _python_skeleton,
            ".ts": _ts_js_skeleton,
            ".tsx": _ts_js_skeleton,
            ".js": _ts_js_skeleton,
            ".jsx": _ts_js_skeleton,
            ".go": _go_skeleton,
            ".java": _java_skeleton,
            ".rs": _rust_skeleton,
            ".rb": _ruby_skeleton,
        }

        handler = handlers.get(suffix, _generic_skeleton)
        skeleton = handler(content)

        if not skeleton or len(skeleton) >= len(content) * 0.8:
            return content, 0

        out = f"[SKELETON: {file_path}]\n{skeleton}"
        after = _est(out)
        return out, max(0, before - after)


# ──────────────────────── language handlers ────────────────────────────────

def _python_skeleton(src: str) -> str:
    lines: list[str] = []
    in_func_body = False
    indent_level = 0

    for line in src.splitlines():
        stripped = stripped_line = line.strip()

        # imports
        if stripped.startswith(("import ", "from ")):
            lines.append(line)
            continue

        # class def
        if re.match(r"^class\s+\w+", stripped):
            lines.append(line)
            in_func_body = False
            continue

        # function / method signatures
        if re.match(r"^(async\s+)?def\s+\w+", stripped):
            lines.append(line)
            in_func_body = True
            continue

        # decorators
        if stripped.startswith("@"):
            lines.append(line)
            continue

        # module-level constants / type aliases (short)
        if re.match(r"^[A-Z_]{2,}\s*=", stripped) and len(line) < 120:
            lines.append(line)
            continue

        # docstring first line
        if in_func_body and stripped.startswith('"""') and len(stripped) > 3:
            short = stripped[:80].rstrip('"').rstrip()
            lines.append(" " * (len(line) - len(line.lstrip())) + short + ' ..."""')
            in_func_body = False
            continue

    return "\n".join(lines)


def _ts_js_skeleton(src: str) -> str:
    lines: list[str] = []
    for line in src.splitlines():
        s = line.strip()
        # imports / exports
        if s.startswith(("import ", "export ", "require(")):
            lines.append(line)
            continue
        # function / class / interface / type declarations
        if re.match(r"^(export\s+)?(async\s+)?function\s+", s):
            lines.append(line)
            continue
        if re.match(r"^(export\s+)?(default\s+)?class\s+", s):
            lines.append(line)
            continue
        if re.match(r"^(export\s+)?(interface|type|enum)\s+", s):
            lines.append(line)
            continue
        # const function expressions
        if re.match(r"^(export\s+)?(const|let|var)\s+\w+\s*[=:]\s*(async\s+)?\(", s):
            lines.append(line)
            continue
        # decorators
        if s.startswith("@"):
            lines.append(line)
            continue
    return "\n".join(lines)


def _go_skeleton(src: str) -> str:
    lines: list[str] = []
    for line in src.splitlines():
        s = line.strip()
        if s.startswith(("package ", "import ", "type ", "const ", "var ")):
            lines.append(line)
        elif re.match(r"^func\s+", s):
            lines.append(line)
    return "\n".join(lines)


def _java_skeleton(src: str) -> str:
    lines: list[str] = []
    for line in src.splitlines():
        s = line.strip()
        if s.startswith(("package ", "import ")):
            lines.append(line)
        elif re.match(r"^(public|private|protected|abstract|static|final|class|interface|enum)", s):
            lines.append(line)
    return "\n".join(lines)


def _rust_skeleton(src: str) -> str:
    lines: list[str] = []
    for line in src.splitlines():
        s = line.strip()
        if s.startswith(("use ", "mod ", "pub mod ", "extern crate")):
            lines.append(line)
        elif re.match(r"^(pub\s+)?(async\s+)?fn\s+", s):
            lines.append(line)
        elif re.match(r"^(pub\s+)?(struct|enum|trait|impl|type)\s+", s):
            lines.append(line)
    return "\n".join(lines)


def _ruby_skeleton(src: str) -> str:
    lines: list[str] = []
    for line in src.splitlines():
        s = line.strip()
        if re.match(r"^(require|include|module|class|def)\s+", s):
            lines.append(line)
        elif s.startswith("attr_"):
            lines.append(line)
    return "\n".join(lines)


def _generic_skeleton(src: str) -> str:
    """Generic: first 40 lines as summary."""
    lines = src.splitlines()
    if len(lines) <= 40:
        return src
    return "\n".join(lines[:40]) + f"\n... ({len(lines) - 40} more lines)"


def _est(t: str) -> int:
    return max(1, len(t) // 4)
