"""
Stop-word removal compressor.
Removes filler words and low-information content.
Example: "I was actually wondering if maybe you could possibly tell me" → "Tell me"
"""

from __future__ import annotations

import re


# Common English stop words (high-information kept)
STOP_WORDS = {
    'actually', 'basically', 'certainly', 'definitely', 'essentially',
    'generally', 'honestly', 'literally', 'maybe', 'possibly', 'probably',
    'really', 'simply', 'sort of', 'kind of', 'a bit', 'a lot',
    'i mean', 'you know', 'like', 'just', 'very', 'quite',
}

# Filler phrases
FILLER_PATTERNS = [
    (r'(?i)\b(i was|i am) (actually |basically |just )?wondering (if|whether)\b', ''),
    (r'(?i)\b(could you|can you) (please |possibly |maybe )?', ''),
    (r'(?i)\b(i would|i\'d) (really |very much )?appreciate (it )?if\b', ''),
    (r'(?i)\b(it would be|it\'d be) (great|nice|helpful) if\b', ''),
    (r'(?i)\b(i\'m|i am) (kind of|sort of) (wondering|thinking)\b', 'wondering'),
    (r'(?i)\b(do you think|could you tell me) (that )?\b', ''),
]


class StopWordRemover:
    """Remove filler words and low-information content."""
    
    def __init__(self, aggressive: bool = False):
        """
        Args:
            aggressive: If True, remove more stop words (may affect meaning)
        """
        self.aggressive = aggressive
        self._compiled_patterns = [(re.compile(p, re.IGNORECASE), r) for p, r in FILLER_PATTERNS]
    
    def compress(self, text: str) -> tuple[str, int]:
        """
        Remove filler words and phrases.
        
        Returns:
            (compressed_text, tokens_saved)
        """
        if not text:
            return text, 0
        
        before_tokens = _estimate_tokens(text)
        result = text
        
        # Remove filler patterns
        for pattern, replacement in self._compiled_patterns:
            result = pattern.sub(replacement, result)
        
        # Remove isolated stop words (careful not to break meaning)
        if self.aggressive:
            words = result.split()
            filtered = []
            for i, word in enumerate(words):
                word_lower = word.lower().strip('.,!?;:')
                # Keep stop word if it's the only word or at sentence boundary
                if word_lower in STOP_WORDS and i > 0 and i < len(words) - 1:
                    continue
                filtered.append(word)
            result = ' '.join(filtered)
        
        # Clean up extra whitespace
        result = re.sub(r'\s+', ' ', result).strip()
        
        after_tokens = _estimate_tokens(result)
        return result, max(0, before_tokens - after_tokens)


def _estimate_tokens(text: str) -> int:
    """Estimate token count (4 chars per token)."""
    return max(1, len(text) // 4)
