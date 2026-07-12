"""Message compression for GitHub Copilot using TrimP algorithms."""

from typing import List, Dict, Any, Tuple

# Import the real TrimP compression algorithms
try:
    from TrimP.compression.prompt_compression import PromptCompressor
    from TrimP.compression.stopword_removal import StopWordRemover
    HAS_ADVANCED = True
except ImportError:
    HAS_ADVANCED = False
    PromptCompressor = None
    StopWordRemover = None


def compress_messages(messages: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Compress chat messages using TrimP algorithms.
    
    Uses PromptCompressor and StopWordRemover for 20-40% compression.
    """
    compressed = []
    original_length = 0
    compressed_length = 0
    
    # Initialize compressors
    prompt_compressor = PromptCompressor() if HAS_ADVANCED else None
    stopword_remover = StopWordRemover(aggressive=False) if HAS_ADVANCED else None
    
    for msg in messages:
        original_content = msg.get("content", "")
        original_length += len(original_content)
        compressed_content = original_content
        
        # Apply compression based on role
        role = msg.get("role", "user")
        
        if HAS_ADVANCED:
            # System and user messages: aggressive compression
            if role in ["system", "user"] and prompt_compressor:
                compressed_content, _ = prompt_compressor.compress(compressed_content)
            
            # All messages: remove stopwords
            if stopword_remover:
                compressed_content, _ = stopword_remover.compress(compressed_content)
        
        # Basic cleanup
        compressed_content = compressed_content.strip()
        compressed_length += len(compressed_content)
        
        # Create compressed message
        compressed_msg = msg.copy()
        compressed_msg["content"] = compressed_content
        compressed.append(compressed_msg)
    
    # Calculate stats
    compression_ratio = 1.0 - (compressed_length / original_length) if original_length > 0 else 0.0
    
    stats = {
        "original_chars": original_length,
        "compressed_chars": compressed_length,
        "compression_ratio": compression_ratio,
        "bytes_saved": original_length - compressed_length,
        "algorithm": "PromptCompressor+StopWords" if HAS_ADVANCED else "basic"
    }
    
    return compressed, stats


if __name__ == '__main__':
    # Test compression
    test_messages = [
        {
            "role": "user",
            "content": """

Please   review   this   code:


def hello():
    # This is a comment
    print("hello")


    
"""
        }
    ]
    
    compressed, stats = compress_messages(test_messages)
    print("Original:", repr(test_messages[0]["content"]))
    print("Compressed:", repr(compressed[0]["content"]))
    print("Stats:", stats)
