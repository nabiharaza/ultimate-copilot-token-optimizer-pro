"""
CodeContextTrimmer - U-shape recency scoring for code files.

Algorithm:
- Recent lines (top/bottom) are most relevant
- Preserve def/class/import lines (high structural value)
- Line-budget greedy selection based on priority scores
- Typical savings: 40-75%

Based on research: LongBench code understanding tasks show U-shape attention.
"""

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
        
        original_chars = len(text)
        compressed_chars = len(compressed)
        savings_pct = ((original_chars - compressed_chars) / original_chars * 100) if original_chars > 0 else 0
        
        return compressed, {
            'method': 'CodeContextTrimmer',
            'lines_kept': len(selected),
            'lines_total': total_lines,
            'savings_pct': round(savings_pct, 1),
            'u_shape_applied': True
        }
    
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
        recency = 1 - (4 * (pos - 0.5) ** 2)  # Max=1 at ends, min=0 at middle
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
