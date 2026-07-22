"""
LogExtractor - Extract errors and warnings from logs.

Algorithm:
- Classify lines: ERROR > WARN > INFO > DEBUG > TRACE
- Deduplicate repeated messages
- Error-context window (keep N lines before/after errors)
- Priority fill remaining budget with warnings
- Typical savings: 50-80%

Based on: Log analysis best practices and error triaging.
"""

import re
from typing import List, Dict, Tuple
from collections import Counter

# Precompiled once — used to remove dates/times/numbers when deduplicating,
# on the same per-line hot path as LEVEL_PATTERNS below.
_DATE_PATTERN = re.compile(r'\d{4}-\d{2}-\d{2}')
_TIME_PATTERN = re.compile(r'\d{2}:\d{2}:\d{2}')
_NUMBER_PATTERN = re.compile(r'\b\d+\b')
_EXTRA_WHITESPACE = re.compile(r'\s+')


class LogExtractor:
    """Extract critical information from log files."""

    # Log level patterns (order matters: most specific first). Compiled once
    # per pattern with IGNORECASE baked in, since _classify_line runs every
    # pattern against every line of the log — the hottest loop in this module.
    LEVEL_PATTERNS = [
        (re.compile(r'\b(ERROR|FATAL|CRITICAL|Exception|Error|Failed|Failure)\b', re.IGNORECASE), 'ERROR', 100),
        (re.compile(r'\b(WARN|WARNING|Deprecated)\b', re.IGNORECASE), 'WARN', 50),
        (re.compile(r'\b(INFO|Information)\b', re.IGNORECASE), 'INFO', 10),
        (re.compile(r'\b(DEBUG|VERBOSE)\b', re.IGNORECASE), 'DEBUG', 5),
        (re.compile(r'\b(TRACE|FINE|FINEST)\b', re.IGNORECASE), 'TRACE', 1),
    ]

    def __init__(self, context_lines: int = 2, target_ratio: float = 0.3):
        """
        Args:
            context_lines: Lines of context to keep around errors
            target_ratio: Target to keep (0.3 = keep 30%, drop 70%)
        """
        self.context_lines = context_lines
        self.target_ratio = target_ratio
    
    def compress(self, text: str) -> Tuple[str, dict]:
        """
        Extract critical log information.
        
        Returns:
            (compressed_log, metadata)
        """
        lines = text.split('\n')
        total_lines = len(lines)
        
        if total_lines < 8:
            # Too short to compress
            return text, {
                'method': 'LogExtractor',
                'lines_kept': total_lines,
                'lines_total': total_lines,
                'savings_pct': 0
            }
        
        # Classify each line
        classified = []
        for idx, line in enumerate(lines):
            level, priority = self._classify_line(line)
            classified.append({
                'idx': idx,
                'line': line,
                'level': level,
                'priority': priority
            })
        
        # Deduplicate
        classified = self._deduplicate(classified)
        
        # Extract errors with context
        error_indices = {c['idx'] for c in classified if c['level'] == 'ERROR'}
        context_indices = set()
        for err_idx in error_indices:
            for offset in range(-self.context_lines, self.context_lines + 1):
                ctx_idx = err_idx + offset
                if 0 <= ctx_idx < total_lines:
                    context_indices.add(ctx_idx)
        
        # Calculate target line count
        target_lines = max(int(total_lines * self.target_ratio), len(context_indices))
        
        # Priority fill remaining budget
        selected_indices = context_indices.copy()
        remaining_budget = target_lines - len(selected_indices)
        
        if remaining_budget > 0:
            # Sort by priority descending
            candidates = [c for c in classified if c['idx'] not in selected_indices]
            candidates.sort(key=lambda x: x['priority'], reverse=True)
            
            for c in candidates[:remaining_budget]:
                selected_indices.add(c['idx'])
        
        # Build result
        selected_indices = sorted(selected_indices)
        result_lines = []
        last_idx = -1
        
        for idx in selected_indices:
            if idx > last_idx + 1:
                # Gap detected
                gap_size = idx - last_idx - 1
                result_lines.append(f'... [{gap_size} lines skipped]')
            result_lines.append(lines[idx])
            last_idx = idx
        
        compressed = '\n'.join(result_lines)
        
        # Stats
        level_counts = Counter(c['level'] for c in classified)
        original_chars = len(text)
        compressed_chars = len(compressed)
        savings_pct = ((original_chars - compressed_chars) / original_chars * 100) if original_chars > 0 else 0
        
        return compressed, {
            'method': 'LogExtractor',
            'lines_kept': len(selected_indices),
            'lines_total': total_lines,
            'savings_pct': round(savings_pct, 1),
            'errors_found': level_counts.get('ERROR', 0),
            'warnings_found': level_counts.get('WARN', 0)
        }
    
    def _classify_line(self, line: str) -> Tuple[str, int]:
        """Classify a log line by level and priority."""
        for pattern, level, priority in self.LEVEL_PATTERNS:
            if pattern.search(line):
                return level, priority
        
        # Default: unknown/info
        return 'INFO', 10
    
    def _deduplicate(self, classified: List[Dict]) -> List[Dict]:
        """Deduplicate repeated log messages."""
        seen = {}
        result = []
        
        for c in classified:
            # Extract message (remove timestamps, numbers)
            normalized = _DATE_PATTERN.sub('', c['line'])  # Remove dates
            normalized = _TIME_PATTERN.sub('', normalized)  # Remove times
            normalized = _NUMBER_PATTERN.sub('N', normalized)  # Replace numbers
            normalized = _EXTRA_WHITESPACE.sub(' ', normalized).strip()
            
            if normalized in seen:
                # Duplicate, update count
                seen[normalized]['count'] += 1
                seen[normalized]['last_idx'] = c['idx']
            else:
                # New message
                seen[normalized] = {
                    'item': c,
                    'count': 1,
                    'last_idx': c['idx']
                }
        
        # Build result with deduplicated messages
        for normalized, info in seen.items():
            c = info['item']
            if info['count'] > 1:
                # Add count suffix
                c['line'] = f"{c['line']} [repeated {info['count']}x]"
            result.append(c)
        
        return result


def compress_log(text: str, context_lines: int = 2, target_ratio: float = 0.3) -> Tuple[str, dict]:
    """
    Convenience function for log extraction.
    
    Args:
        text: Log file content
        context_lines: Context around errors
        target_ratio: How much to keep
    
    Returns:
        (compressed_log, metadata)
    """
    extractor = LogExtractor(context_lines=context_lines, target_ratio=target_ratio)
    return extractor.compress(text)
