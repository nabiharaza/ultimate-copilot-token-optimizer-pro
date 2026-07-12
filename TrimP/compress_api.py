"""
Simple compression API - Always uses best compression automatically.

This is the main entry point for compression. Just call compress_text()
and it will automatically choose the best algorithm and settings.

Example:
    from TrimP.compress_api import compress_text
    
    result = compress_text("Your long text here...")
    print(f"Saved {result['tokens_saved']} tokens ({result['savings_pct']:.1f}%)")
"""

from typing import Dict, Any, Tuple
from TrimP.compression.advanced.universal_optimizer import UniversalOptimizer

# Global instance with aggressive mode enabled by default
_optimizer = UniversalOptimizer(aggressive=True)


def compress_text(text: str, hint: str = None) -> Dict[str, Any]:
    """
    Compress any text using the best algorithm automatically.
    
    This function:
    - Auto-detects input type (code, JSON, logs, chat, etc.)
    - Uses the most aggressive compression settings
    - Returns detailed metrics
    
    Args:
        text: Any text to compress
        hint: Optional hint ('code', 'json', 'log', 'chat', 'doc')
    
    Returns:
        {
            'original': str,        # Original text
            'compressed': str,      # Compressed text
            'tokens_saved': int,    # Tokens saved
            'savings_pct': float,   # Savings percentage
            'method': str,          # Algorithm used
            'metadata': dict        # Full metadata
        }
    
    Example:
        >>> result = compress_text("def hello(): pass\\n" * 100)
        >>> print(f"Saved {result['savings_pct']:.1f}%")
        Saved 57.6%
    """
    # Compress
    compressed, metadata = _optimizer.compress(text, hint=hint)
    
    # Calculate tokens (rough estimate: 1 token ≈ 4 chars)
    original_tokens = len(text) // 4
    compressed_tokens = len(compressed) // 4
    tokens_saved = original_tokens - compressed_tokens
    
    # Build result
    return {
        'original': text,
        'compressed': compressed,
        'original_length': len(text),
        'compressed_length': len(compressed),
        'original_tokens': original_tokens,
        'compressed_tokens': compressed_tokens,
        'tokens_saved': tokens_saved,
        'savings_pct': metadata.get('savings_pct', 0.0),
        'method': metadata.get('method', 'Unknown'),
        'routed_to': metadata.get('routed_to', None),
        'metadata': metadata
    }


def compress_simple(text: str) -> str:
    """
    Simplest API - just compress and return the text.
    
    Args:
        text: Text to compress
    
    Returns:
        Compressed text (string)
    
    Example:
        >>> compressed = compress_simple("Very long text...")
        >>> print(compressed)
    """
    compressed, _ = _optimizer.compress(text)
    return compressed


def get_compression_stats(text: str, hint: str = None) -> Dict[str, Any]:
    """
    Get compression statistics without returning the full text.
    
    Useful for analyzing how well something would compress without
    storing the full result.
    
    Args:
        text: Text to analyze
        hint: Optional type hint
    
    Returns:
        {
            'original_tokens': int,
            'compressed_tokens': int,
            'tokens_saved': int,
            'savings_pct': float,
            'method': str
        }
    """
    result = compress_text(text, hint)
    return {
        'original_tokens': result['original_tokens'],
        'compressed_tokens': result['compressed_tokens'],
        'tokens_saved': result['tokens_saved'],
        'savings_pct': result['savings_pct'],
        'method': result['method'],
        'routed_to': result.get('routed_to')
    }


# Convenience exports
__all__ = [
    'compress_text',      # Full API with metrics
    'compress_simple',    # Simple string → string
    'get_compression_stats'  # Just stats, no text
]
