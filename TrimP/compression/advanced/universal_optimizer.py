"""
UniversalOptimizer - Intelligent routing to the right algorithm.

Algorithm:
- Heuristic detection of input type
- Routes to specialized compressor
- Fallback to generic compression
- Typical savings: varies by input

Meta-algorithm that orchestrates all others.
"""

import json
import re
from typing import Tuple, Dict

from .code_context_trimmer import compress_code_context
from .conversation_compressor import compress_conversation
from .json_minimizer import compress_json
from .log_extractor import compress_log
from .semantic_chunker import compress_semantic
from .llm_lingua_lite import compress_llm_lingua


class UniversalOptimizer:
    """Route input to the best compression algorithm."""
    
    def __init__(self, aggressive: bool = True):
        """
        Args:
            aggressive: Use more aggressive compression settings (default: True for maximum savings)
        """
        self.aggressive = aggressive
    
    def compress(self, text: str, hint: str = None) -> Tuple[str, dict]:
        """
        Compress text using the best algorithm for its type.
        
        Args:
            text: Input text
            hint: Optional hint about input type ('code', 'json', 'log', 'chat', 'doc')
        
        Returns:
            (compressed_text, metadata)
        """
        if hint:
            # Use hint
            compressed, metadata = self._compress_with_hint(text, hint)
        else:
            # Auto-detect
            input_type = self._detect_type(text)
            compressed, metadata = self._compress_by_type(text, input_type)
        
        # Ensure UniversalOptimizer is in metadata
        if 'method' not in metadata or metadata['method'] != 'UniversalOptimizer':
            original_method = metadata.get('method', 'Unknown')
            metadata['method'] = 'UniversalOptimizer'
            metadata['routed_to'] = original_method
        
        return compressed, metadata
    
    def _detect_type(self, text: str) -> str:
        """Detect input type using heuristics."""
        # Try JSON
        try:
            json.loads(text)
            return 'json'
        except:
            pass
        
        # Check for chat conversation (alternating user/assistant)
        if re.search(r'(user:|assistant:|role|content)', text, re.IGNORECASE):
            return 'chat'
        
        # Check for code (many def/class/import keywords)
        code_keywords = len(re.findall(r'\b(def |class |import |from |function |const |let |var |public |private)\b', text))
        if code_keywords > 3:
            return 'code'
        
        # Check for logs (timestamps, log levels)
        log_patterns = len(re.findall(r'(\d{4}-\d{2}-\d{2}|\d{2}:\d{2}:\d{2}|ERROR|WARN|INFO|DEBUG)', text))
        if log_patterns > 5:
            return 'log'
        
        # Default: generic document
        return 'doc'
    
    def _compress_with_hint(self, text: str, hint: str) -> Tuple[str, dict]:
        """Compress using hint."""
        hint = hint.lower()
        
        if hint == 'code':
            ratio = 0.3 if self.aggressive else 0.4
            return compress_code_context(text, target_ratio=ratio)
        elif hint == 'json':
            return compress_json(text, max_depth=3 if self.aggressive else 4)
        elif hint == 'log':
            ratio = 0.2 if self.aggressive else 0.3
            return compress_log(text, target_ratio=ratio)
        elif hint == 'chat':
            # Can't compress without structure
            return text, {'method': 'UniversalOptimizer', 'error': 'Chat needs structured input', 'savings_pct': 0}
        elif hint == 'doc':
            ratio = 0.4 if self.aggressive else 0.5
            return compress_llm_lingua(text, target_ratio=ratio)
        else:
            return text, {'method': 'UniversalOptimizer', 'error': f'Unknown hint: {hint}', 'savings_pct': 0}
    
    def _compress_by_type(self, text: str, input_type: str) -> Tuple[str, dict]:
        """Compress based on detected type."""
        try:
            if input_type == 'code':
                ratio = 0.3 if self.aggressive else 0.4
                return compress_code_context(text, target_ratio=ratio)
            elif input_type == 'json':
                return compress_json(text, max_depth=3 if self.aggressive else 4)
            elif input_type == 'log':
                ratio = 0.2 if self.aggressive else 0.3
                return compress_log(text, target_ratio=ratio)
            elif input_type == 'chat':
                # Can't detect structure, use generic
                ratio = 0.4 if self.aggressive else 0.5
                return compress_llm_lingua(text, target_ratio=ratio)
            else:  # doc
                ratio = 0.4 if self.aggressive else 0.5
                return compress_llm_lingua(text, target_ratio=ratio)
        except Exception as e:
            # Fallback: generic compression
            return compress_llm_lingua(text, target_ratio=0.5)


def compress_universal(text: str, hint: str = None, aggressive: bool = False) -> Tuple[str, dict]:
    """
    Convenience function for universal optimization.
    
    Args:
        text: Input text
        hint: Optional type hint
        aggressive: Use aggressive settings
    
    Returns:
        (compressed_text, metadata)
    """
    optimizer = UniversalOptimizer(aggressive=aggressive)
    return optimizer.compress(text, hint=hint)
