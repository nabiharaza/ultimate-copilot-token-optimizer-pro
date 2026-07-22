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
from TrimP.compression.advanced.llmlingua2 import LLMLingua2Compressor
from TrimP.compression.advanced.universal_optimizer import UniversalOptimizer
from TrimP.tokenization import count_tokens

# Balanced and verification-friendly by default. Aggressive compression is a
# per-policy choice, not a process-global hidden default.
_shared_learned = LLMLingua2Compressor()
_optimizers = {
    'conservative': UniversalOptimizer(aggressive=False),
    'balanced': UniversalOptimizer(aggressive=False),
    'aggressive': UniversalOptimizer(aggressive=True),
}
for _optimizer in _optimizers.values():
    _optimizer.learned = _shared_learned


def warm_learned_compressor() -> None:
    """Begin loading the shared learned model for long-lived proxy workers."""
    _shared_learned.warm_async()


def compress_text(
    text: str,
    hint: str = None,
    *,
    query: str = "",
    model: str | None = None,
    policy: str = "balanced",
) -> Dict[str, Any]:
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
    selected_policy = str(policy or "balanced").lower()
    optimizer = _optimizers.get(selected_policy, _optimizers['balanced'])
    compressed, metadata = optimizer.compress(text, hint=hint, query=query, model=model)
    metadata['policy'] = selected_policy if selected_policy in _optimizers else 'balanced'
    
    original_count = count_tokens(text, model=model)
    compressed_count = count_tokens(compressed, model=model)
    original_tokens = original_count.tokens
    compressed_tokens = compressed_count.tokens
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
        'tokenizer': original_count.tokenizer,
        'token_count_exact': original_count.exact_for_serialized_input,
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
    compressed, _ = _optimizers['balanced'].compress(text)
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
