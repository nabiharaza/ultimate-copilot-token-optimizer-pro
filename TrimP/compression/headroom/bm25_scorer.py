"""BM25 relevance scorer (adapted from Headroom SDK).

Pure Python, zero dependencies. Excellent for keyword-based relevance ranking.

Original: headroom/relevance/bm25.py
Adapted for TrimP compression use cases.
"""

import math
import re
from collections import Counter
from typing import List, Tuple


class BM25Scorer:
    """BM25 keyword relevance scorer.

    Zero dependencies, instant execution. Excellent for exact ID/UUID matching
    and keyword-based text ranking.

    BM25 formula:
        score(D, Q) = sum over q in Q of:
            IDF(q) * (f(q,D) * (k1 + 1)) / (f(q,D) + k1 * (1 - b + b * |D|/avgdl))

    Where:
        - f(q,D) = frequency of term q in document D
        - |D| = length of document D
        - avgdl = average document length
        - k1, b = tuning parameters
    """

    # Tokenization pattern: alphanumeric sequences, UUIDs, numeric IDs
    _TOKEN_PATTERN = re.compile(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"  # UUIDs
        r"|\b\d{4,}\b"  # Numeric IDs (4+ digits)
        r"|[a-zA-Z0-9_]+"  # Alphanumeric tokens
    )

    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        normalize_score: bool = True,
        max_score: float = 10.0,
    ):
        """Initialize BM25 scorer.

        Args:
            k1: Term frequency saturation parameter (default 1.5).
            b: Length normalization parameter (default 0.75).
            normalize_score: If True, normalize score to [0, 1].
            max_score: Maximum raw score for normalization.
        """
        self.k1 = k1
        self.b = b
        self.normalize_score = normalize_score
        self.max_score = max_score

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into terms.

        Preserves UUIDs, numeric IDs, and alphanumeric words.
        """
        if not text:
            return []
        return self._TOKEN_PATTERN.findall(text.lower())

    def _bm25_score(
        self,
        doc_tokens: List[str],
        query_tokens: List[str],
        avg_doc_len: float = None,
    ) -> Tuple[float, List[str]]:
        """Compute BM25 score between document and query."""
        if not doc_tokens or not query_tokens:
            return 0.0, []

        doc_len = len(doc_tokens)
        avgdl = avg_doc_len or doc_len or 1

        doc_freq = Counter(doc_tokens)
        query_freq = Counter(query_tokens)

        score = 0.0
        matched_terms: List[str] = []

        for term, qf in query_freq.items():
            if term not in doc_freq:
                continue

            f = doc_freq[term]
            matched_terms.append(term)

            # BM25 term score (simplified, single-doc IDF = log(2))
            idf = math.log(2.0)
            numerator = f * (self.k1 + 1)
            denominator = f + self.k1 * (1 - self.b + self.b * doc_len / avgdl)

            term_score = idf * numerator / denominator
            score += term_score * qf

        return score, matched_terms

    def score(self, item: str, query: str) -> Tuple[float, List[str]]:
        """Score item relevance to query using BM25.

        Args:
            item: Item text to score.
            query: Query context.

        Returns:
            Tuple of (score, matched_terms).
        """
        item_tokens = self._tokenize(item)
        query_tokens = self._tokenize(query)

        raw_score, matched = self._bm25_score(item_tokens, query_tokens)

        # Normalize to [0, 1]
        if self.normalize_score:
            normalized = min(1.0, raw_score / self.max_score)
        else:
            normalized = raw_score

        # Bonus for exact long-token matches (UUIDs, long IDs)
        # High bonus to ensure UUIDs/IDs are prioritized for retention
        long_matches = [t for t in matched if len(t) >= 8]
        if long_matches:
            normalized = min(1.0, normalized * 2.0)  # Double score for long matches

        return normalized, matched

    def score_batch(
        self, items: List[str], query: str
    ) -> List[Tuple[float, List[str]]]:
        """Score multiple items against query.

        Args:
            items: List of items to score.
            query: Query context.

        Returns:
            List of (score, matched_terms) tuples.
        """
        query_tokens = self._tokenize(query)

        if not query_tokens:
            return [(0.0, []) for _ in items]

        # Compute average document length for normalization
        all_tokens = [self._tokenize(item) for item in items]
        avg_len = sum(len(t) for t in all_tokens) / max(len(items), 1)

        results = []
        for item_tokens in all_tokens:
            raw_score, matched = self._bm25_score(item_tokens, query_tokens, avg_len)

            # Normalize
            if self.normalize_score:
                normalized = min(1.0, raw_score / self.max_score)
            else:
                normalized = raw_score

            # Bonus for long matches
            long_matches = [t for t in matched if len(t) >= 8]
            if long_matches:
                normalized = min(1.0, normalized + 0.3)

            results.append((normalized, matched))

        return results
