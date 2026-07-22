"""
Skeleton compressor — file structure maps.
720KB → ~250 tokens (signatures + imports only).
"""

from __future__ import annotations

import re
from pathlib import Path

# Precompiled once at import time and reused for every line of every file
# compressed (these run in a tight per-line loop, so avoiding re-parsing the
# pattern string on each call matters here more than in the other compressors).
_PY_CLASS = re.compile(r"^class\s+\w+")
_PY_DEF = re.compile(r"^(async\s+)?def\s+\w+")
_PY_CONST = re.compile(r"^[A-Z_]{2,}\s*=")

_TS_FUNCTION = re.compile(r"^(export\s+)?(async\s+)?function\s+")
_TS_CLASS = re.compile(r"^(export\s+)?(default\s+)?class\s+")
_TS_TYPE = re.compile(r"^(export\s+)?(interface|type|enum)\s+")
_TS_CONST_FN = re.compile(r"^(export\s+)?(const|let|var)\s+\w+\s*[=:]\s*(async\s+)?\(")

_GO_FUNC = re.compile(r"^func\s+")

_JAVA_MEMBER = re.compile(r"^(public|private|protected|abstract|static|final|class|interface|enum)")

_RUST_FN = re.compile(r"^(pub\s+)?(async\s+)?fn\s+")
_RUST_TYPE = re.compile(r"^(pub\s+)?(struct|enum|trait|impl|type)\s+")

_RUBY_DECL = re.compile(r"^(require|include|module|class|def)\s+")


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
        if _PY_CLASS.match(stripped):
            lines.append(line)
            in_func_body = False
            continue

        # function / method signatures
        if _PY_DEF.match(stripped):
            lines.append(line)
            in_func_body = True
            continue

        # decorators
        if stripped.startswith("@"):
            lines.append(line)
            continue

        # module-level constants / type aliases (short)
        if _PY_CONST.match(stripped) and len(line) < 120:
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
        if _TS_FUNCTION.match(s):
            lines.append(line)
            continue
        if _TS_CLASS.match(s):
            lines.append(line)
            continue
        if _TS_TYPE.match(s):
            lines.append(line)
            continue
        # const function expressions
        if _TS_CONST_FN.match(s):
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
        elif _GO_FUNC.match(s):
            lines.append(line)
    return "\n".join(lines)


def _java_skeleton(src: str) -> str:
    lines: list[str] = []
    for line in src.splitlines():
        s = line.strip()
        if s.startswith(("package ", "import ")):
            lines.append(line)
        elif _JAVA_MEMBER.match(s):
            lines.append(line)
    return "\n".join(lines)


def _rust_skeleton(src: str) -> str:
    lines: list[str] = []
    for line in src.splitlines():
        s = line.strip()
        if s.startswith(("use ", "mod ", "pub mod ", "extern crate")):
            lines.append(line)
        elif _RUST_FN.match(s):
            lines.append(line)
        elif _RUST_TYPE.match(s):
            lines.append(line)
    return "\n".join(lines)


def _ruby_skeleton(src: str) -> str:
    lines: list[str] = []
    for line in src.splitlines():
        s = line.strip()
        if _RUBY_DECL.match(s):
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
    from TrimP.tokenization import count_tokens

    return count_tokens(t).tokens
