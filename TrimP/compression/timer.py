"""
Compression timing tracker.
Records time spent in each compression stage.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from contextlib import contextmanager


@dataclass
class CompressionTimer:
    """Track compression performance metrics."""
    
    total: float = 0.0
    receive: float = 0.0
    compress: float = 0.0
    algorithm: float = 0.0
    respond: float = 0.0
    
    _start: float = field(default=0.0, init=False, repr=False)
    
    def start(self):
        """Start timing."""
        self._start = time.perf_counter()
    
    def stop(self):
        """Stop timing and record total."""
        if self._start > 0:
            self.total = time.perf_counter() - self._start
    
    @contextmanager
    def stage(self, stage_name: str):
        """Context manager for timing a stage."""
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start
            if hasattr(self, stage_name):
                setattr(self, stage_name, duration)
    
    def get_report(self) -> dict:
        """Get timing report with breakdown."""
        total_ms = self.total * 1000
        
        return {
            'total_ms': round(total_ms, 2),
            'breakdown': {
                'receive_ms': round(self.receive * 1000, 2),
                'compress_ms': round(self.compress * 1000, 2),
                'algorithm_ms': round(self.algorithm * 1000, 2),
                'respond_ms': round(self.respond * 1000, 2),
            },
            'percentages': {
                'receive': round((self.receive / self.total * 100), 1) if self.total > 0 else 0,
                'compress': round((self.compress / self.total * 100), 1) if self.total > 0 else 0,
                'algorithm': round((self.algorithm / self.total * 100), 1) if self.total > 0 else 0,
                'respond': round((self.respond / self.total * 100), 1) if self.total > 0 else 0,
            }
        }
    
    def print_report(self):
        """Print formatted timing report."""
        report = self.get_report()
        print(f"\n┌{'─' * 40}┐")
        print(f"│ {'Compression Performance':<38} │")
        print(f"├{'─' * 40}┤")
        print(f"│ Total Time: {report['total_ms']:>8.2f}ms{' ' * 19}│")
        print(f"│   • Receive:   {report['breakdown']['receive_ms']:>7.2f}ms ({report['percentages']['receive']:>5.1f}%) │")
        print(f"│   • Compress:  {report['breakdown']['compress_ms']:>7.2f}ms ({report['percentages']['compress']:>5.1f}%) │")
        print(f"│   • Algorithm: {report['breakdown']['algorithm_ms']:>7.2f}ms ({report['percentages']['algorithm']:>5.1f}%) │")
        print(f"│   • Respond:   {report['breakdown']['respond_ms']:>7.2f}ms ({report['percentages']['respond']:>5.1f}%) │")
        print(f"└{'─' * 40}┘\n")
