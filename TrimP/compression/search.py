"""
Search/grep output compressor.
Returns top hits + count summary.
500 lines → ~20 tokens.
"""

from __future__ import annotations

import re


class SearchCompressor:
    """Compress grep/ripgrep/search output to top hits + summary."""

    def compress(self, text: str, top_n: int = 15) -> tuple[str, int]:
        lines = [l for l in text.strip().splitlines() if l.strip()]
        total = len(lines)

        if total <= top_n:
            return text, 0

        before = _est(text)
        kept = lines[:top_n]
        omitted = total - top_n
        summary = f"\n... {omitted} more results omitted (total: {total} matches)"
        out = "\n".join(kept) + summary
        after = _est(out)
        return out, max(0, before - after)

    def compress_file_list(self, text: str, top_n: int = 20) -> tuple[str, int]:
        """Compress a file listing (ls -la style) to top entries + stats."""
        lines = text.strip().splitlines()
        # Find stat line (total N)
        stat_lines = [l for l in lines if l.startswith("total")]
        file_lines = [l for l in lines if not l.startswith("total") and l.strip()]

        before = _est(text)
        if len(file_lines) <= top_n:
            return text, 0

        kept = stat_lines + file_lines[:top_n]
        omitted = len(file_lines) - top_n
        out = "\n".join(kept) + f"\n... {omitted} more files"
        return out, max(0, before - _est(out))

    def compress_ripgrep(self, text: str, top_files: int = 10, top_per_file: int = 3) -> tuple[str, int]:
        """Compress ripgrep output: keep top N files, top M matches per file."""
        before = _est(text)
        current_file = None
        file_matches: dict[str, list[str]] = {}
        file_order: list[str] = []

        for line in text.splitlines():
            # ripgrep file header (--heading)
            if line and not line.startswith(" ") and ":" not in line[:80] and line.endswith(":"):
                current_file = line.rstrip(":")
                if current_file not in file_matches:
                    file_matches[current_file] = []
                    file_order.append(current_file)
            elif current_file and line.strip():
                if len(file_matches[current_file]) < top_per_file:
                    file_matches[current_file].append(line)
            else:
                # flat ripgrep format: file:line:content
                m = re.match(r"^(.+?):(\d+):(.*)", line)
                if m:
                    fname = m.group(1)
                    if fname not in file_matches:
                        file_matches[fname] = []
                        file_order.append(fname)
                    if len(file_matches[fname]) < top_per_file:
                        file_matches[fname].append(f"  L{m.group(2)}: {m.group(3)}")

        if not file_matches:
            return text, 0

        total_files = len(file_order)
        shown_files = file_order[:top_files]
        out_lines: list[str] = []
        for f in shown_files:
            out_lines.append(f"{f}:")
            out_lines.extend(file_matches[f])
            if len(file_matches[f]) == top_per_file:
                out_lines.append(f"  ...")

        omitted_files = total_files - len(shown_files)
        if omitted_files:
            out_lines.append(f"\n... {omitted_files} more files with matches")

        out = "\n".join(out_lines)
        return out, max(0, before - _est(out))


def _est(t: str) -> int:
    from TrimP.tokenization import count_tokens

    return count_tokens(t).tokens
