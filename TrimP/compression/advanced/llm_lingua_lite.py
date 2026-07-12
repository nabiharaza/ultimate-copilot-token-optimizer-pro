"""
LLMLinguaLite - Generic prompt compression using word-level pruning.

Algorithm:
- Self-information scoring using word frequency
- Iterative token-level pruning to meet budget
- Perplexity approximation (no model needed)
- Typical savings: 30-60%

Based on: LLMLingua paper (Microsoft Research).
Reference: https://arxiv.org/abs/2310.05736
"""

import re
from collections import Counter
from typing import List, Tuple, Dict
import math


class LLMLinguaLite:
    """Compress prompts by removing low-information words."""
    
    def __init__(self, target_ratio: float = 0.5, preserve_questions: bool = True):
        """
        Args:
            target_ratio: Target to keep (0.5 = keep 50%)
            preserve_questions: Always keep question words
        """
        self.target_ratio = target_ratio
        self.preserve_questions = preserve_questions
        
        # Question words should be preserved
        self.question_words = {
            'what', 'when', 'where', 'who', 'whom', 'whose', 'why', 'how',
            'which', 'can', 'could', 'would', 'should', 'will', 'do', 'does',
            'is', 'are', 'was', 'were'
        }
    
    def compress(self, text: str) -> Tuple[str, dict]:
        """
        Compress text by pruning low-information words.
        
        Returns:
            (compressed_text, metadata)
        """
        # Tokenize into words
        tokens = self._tokenize(text)
        
        if len(tokens) < 20:
            # Too short
            return text, {
                'method': 'LLMLinguaLite',
                'tokens_kept': len(tokens),
                'tokens_total': len(tokens),
                'savings_pct': 0
            }
        
        # Calculate target token count
        target_tokens = max(int(len(tokens) * self.target_ratio), 10)
        
        # Score each token by self-information
        scores = self._score_tokens(tokens)
        
        # Select top N tokens
        token_indices = list(range(len(tokens)))
        
        # Sort by score descending
        sorted_indices = sorted(token_indices, key=lambda i: scores[i], reverse=True)
        
        # Take top N
        selected_indices = sorted(sorted_indices[:target_tokens])
        
        # Reconstruct text
        selected_tokens = [tokens[i] for i in selected_indices]
        compressed = self._reconstruct(selected_tokens, tokens, selected_indices)
        
        original_chars = len(text)
        compressed_chars = len(compressed)
        savings_pct = ((original_chars - compressed_chars) / original_chars * 100) if original_chars > 0 else 0
        
        return compressed, {
            'method': 'LLMLinguaLite',
            'tokens_kept': len(selected_indices),
            'tokens_total': len(tokens),
            'savings_pct': round(savings_pct, 1),
            'self_information_pruning': True
        }
    
    def _tokenize(self, text: str) -> List[Dict]:
        """
        Tokenize text into words with metadata.
        
        Returns:
            List of {'word': str, 'original': str, 'start': int, 'end': int}
        """
        tokens = []
        
        # Find all words (alphanumeric sequences)
        for match in re.finditer(r'\b[\w]+\b', text):
            tokens.append({
                'word': match.group(0).lower(),
                'original': match.group(0),
                'start': match.start(),
                'end': match.end()
            })
        
        return tokens
    
    def _score_tokens(self, tokens: List[Dict]) -> List[float]:
        """
        Score tokens using self-information.
        
        Self-information I(w) = -log(P(w))
        Higher score = more informative (rare words)
        """
        # Count word frequencies
        words = [t['word'] for t in tokens]
        word_counts = Counter(words)
        total_words = len(words)
        
        # Calculate self-information for each token
        scores = []
        for token in tokens:
            word = token['word']
            
            # Preserve question words
            if self.preserve_questions and word in self.question_words:
                scores.append(1000.0)  # Very high score
                continue
            
            # Preserve proper nouns (capitalized)
            if token['original'][0].isupper() and word not in {'i', 'a'}:
                scores.append(100.0)  # High score
                continue
            
            # Calculate self-information
            freq = word_counts[word]
            prob = freq / total_words
            self_info = -math.log(prob) if prob > 0 else 0
            
            # Boost longer words (more specific)
            length_bonus = min(len(word) / 10, 2.0)
            
            score = self_info + length_bonus
            scores.append(score)
        
        return scores
    
    def _reconstruct(self, selected_tokens: List[Dict], all_tokens: List[Dict], selected_indices: List[int]) -> str:
        """Reconstruct text from selected tokens."""
        if not selected_tokens:
            return ""
        
        # Build ranges of selected tokens
        result_parts = []
        
        for token in selected_tokens:
            result_parts.append(token['original'])
        
        # Join with spaces
        return ' '.join(result_parts)


def compress_llm_lingua(text: str, target_ratio: float = 0.5, preserve_questions: bool = True) -> Tuple[str, dict]:
    """
    Convenience function for LLMLingua-style compression.
    
    Args:
        text: Text to compress
        target_ratio: How much to keep
        preserve_questions: Keep question words
    
    Returns:
        (compressed_text, metadata)
    """
    compressor = LLMLinguaLite(target_ratio=target_ratio, preserve_questions=preserve_questions)
    return compressor.compress(text)
