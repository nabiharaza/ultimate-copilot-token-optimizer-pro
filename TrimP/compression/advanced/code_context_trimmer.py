"""
CodeContextTrimmer - U-shape recency scoring for code files.

Algorithm:
- Recent lines (top/bottom) are most relevant
- Preserve def/class/import lines (high structural value)
- Line-budget greedy selection based on priority scores
- Typical savings: 40-75%

Based on research: LongBench code understanding tasks show U-shape attention.
"""

import ast
import re
from typing import List, Tuple


class CodeContextTrimmer:
    """Compress code files while preserving critical structure."""
    
    def __init__(self, target_ratio: float = 0.55):
        """
        Args:
            target_ratio: Target to keep (0.55 = keep 55%, drop 45% - increased from 0.4 for better compression)
        """
        self.target_ratio = target_ratio
        self.structural_patterns = [
            r'^\s*(def |class |async def |@)',  # Function/class definitions
            r'^\s*(import |from .* import)',     # Imports
            r'^\s*(interface |type |enum )',     # TypeScript/interfaces
            r'^\s*(public |private |protected)', # Java/C++
            r'^\s*\/\/\s*TODO|FIXME|NOTE',     # Important comments
            r'^\s*export\s+(default\s+)?(class|function|const|let|var)',  # ES6 exports
            r'^\s*return\s',                     # Return statements
        ]
    
    def compress(self, text: str) -> Tuple[str, dict]:
        """
        Compress code using U-shape recency + structural priority.
        
        Returns:
            (compressed_text, metadata)
        """
        deduplicated, repeated_blocks = self._deduplicate_fenced_blocks(text)
        if repeated_blocks:
            savings_pct = ((len(text) - len(deduplicated)) / len(text) * 100) if text else 0
            return deduplicated, {
                'method': 'CodeContextTrimmer',
                'mode': 'lossless-identical-block-deduplication',
                'repeated_blocks_removed': repeated_blocks,
                'lines_kept': len(deduplicated.splitlines()),
                'lines_total': len(text.splitlines()),
                'savings_pct': round(savings_pct, 1),
            }

        lines = text.split('\n')
        total_lines = len(lines)
        
        if total_lines < 15:
            # Too short to compress meaningfully
            return text, {
                'method': 'CodeContextTrimmer',
                'lines_kept': total_lines,
                'lines_total': total_lines,
                'savings_pct': 0
            }
        
        # Calculate target line count - more aggressive
        target_lines = max(int(total_lines * self.target_ratio), 10)
        
        # Score each line
        scored_lines = []
        for idx, line in enumerate(lines):
            score = self._score_line(line, idx, total_lines)
            scored_lines.append((idx, line, score))
        
        # Sort by score descending
        scored_lines.sort(key=lambda x: x[2], reverse=True)
        
        # Take top N lines
        selected = scored_lines[:target_lines]
        
        # Sort by original line number to maintain order
        selected.sort(key=lambda x: x[0])
        
        # Reconstruct with ellipsis markers for dropped sections
        result_lines = []
        last_idx = -1
        for idx, line, score in selected:
            if idx > last_idx + 1:
                # Gap detected, show compact ellipsis
                gap_size = idx - last_idx - 1
                # Only add ellipsis if gap is significant (>2 lines)
                if gap_size > 2:
                    result_lines.append(f'# ...')
            result_lines.append(line)
            last_idx = idx
        
        compressed = '\n'.join(result_lines)
        mode = 'structural-line-selection'
        try:
            ast.parse(text)
        except SyntaxError:
            pass
        else:
            try:
                ast.parse(compressed)
            except SyntaxError:
                compressed = self._python_skeleton(text)
                mode = 'python-ast-skeleton'
        
        original_chars = len(text)
        compressed_chars = len(compressed)
        savings_pct = ((original_chars - compressed_chars) / original_chars * 100) if original_chars > 0 else 0
        
        return compressed, {
            'method': 'CodeContextTrimmer',
            'lines_kept': len(selected),
            'lines_total': total_lines,
            'savings_pct': round(savings_pct, 1),
            'u_shape_applied': True,
            'mode': mode,
        }

    @staticmethod
    def _python_skeleton(text: str) -> str:
        """Build a valid, explicit Python structural view from the AST."""
        tree = ast.parse(text)
        lines: list[str] = []

        def signature(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
            prefix = 'async def' if isinstance(node, ast.AsyncFunctionDef) else 'def'
            return f"{prefix} {node.name}({ast.unparse(node.args)}):"

        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                lines.append(ast.get_source_segment(text, node) or ast.unparse(node))
            elif isinstance(node, ast.ClassDef):
                bases = ', '.join(ast.unparse(base) for base in node.bases)
                lines.append(f"\nclass {node.name}({bases}):" if bases else f"\nclass {node.name}:")
                methods = [item for item in node.body if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))]
                if not methods:
                    lines.append("    pass  # TrimPy: implementation omitted from context")
                for method in methods:
                    lines.append("    " + signature(method))
                    lines.append("        pass  # TrimPy: implementation omitted from context")
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                lines.append("\n" + signature(node))
                lines.append("    pass  # TrimPy: implementation omitted from context")
            elif isinstance(node, (ast.Assign, ast.AnnAssign)):
                segment = ast.get_source_segment(text, node)
                if segment and len(segment) <= 240:
                    lines.append(segment)
        return '\n'.join(lines).strip() + '\n'

    @staticmethod
    def _deduplicate_fenced_blocks(text: str) -> Tuple[str, int]:
        """Remove byte-identical repeated fenced snippets and retain one copy."""
        pattern = re.compile(r"```[^\n]*\n.*?```", re.DOTALL)
        seen: set[str] = set()
        removed = 0

        def replace(match: re.Match[str]) -> str:
            nonlocal removed
            block = match.group(0)
            if block in seen:
                removed += 1
                return ""
            seen.add(block)
            return block

        result = pattern.sub(replace, text)
        if removed:
            result = re.sub(r"\n{3,}", "\n\n", result).rstrip()
            result += f"\n# [TrimPy: {removed} identical fenced code blocks omitted]\n"
        return result, removed
    
    def _score_line(self, line: str, idx: int, total: int) -> float:
        """
        Score a line for importance.
        
        Scoring factors:
        - Recency (U-shape): high at start/end, low in middle
        - Structural: def/class/import get bonus
        - Content: non-empty, non-comment
        """
        score = 0.0
        
        # U-shape recency (parabolic)
        # Normalize position to [0, 1]
        pos = idx / total if total > 1 else 0.5
        # U-shape: high at 0 and 1, low at 0.5
        recency = 4 * (pos - 0.5) ** 2  # Max=1 at ends, min=0 at middle
        score += recency * 5  # Weight recency heavily
        
        # Structural importance
        for pattern in self.structural_patterns:
            if re.match(pattern, line):
                score += 20  # Structural lines are critical
                break
        
        # Content density
        stripped = line.strip()
        if stripped and not stripped.startswith('#') and not stripped.startswith('//'):
            # Non-empty, non-comment
            score += min(len(stripped) / 20, 3)  # Longer lines slightly more valuable
        
        # Penalize pure whitespace or simple braces
        if not stripped or stripped in ['{', '}', '(', ')', '[', ']']:
            score -= 2
        
        return score


def compress_code_context(text: str, target_ratio: float = 0.4) -> Tuple[str, dict]:
    """
    Convenience function for code context trimming.
    
    Args:
        text: Code content
        target_ratio: How much to keep (0.4 = 40%)
    
    Returns:
        (compressed_text, metadata)
    """
    trimmer = CodeContextTrimmer(target_ratio=target_ratio)
    return trimmer.compress(text)
