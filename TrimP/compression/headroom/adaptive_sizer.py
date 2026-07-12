"""Adaptive compression sizing via information saturation detection (from Headroom SDK).

Instead of hardcoded limits, this statistically determines optimal compression size
by finding the "knee point" — where adding more items stops providing meaningful
new information.

Algorithm: Track unique bigrams as items are added in importance order. Build a
cumulative coverage curve. Find the knee (Kneedle algorithm) where marginal
information gain drops sharply.

Original: headroom/transforms/adaptive_sizer.py
Adapted for TrimP compression use cases.
"""

import hashlib
import logging
import zlib
from typing import List, Optional, Sequence

logger = logging.getLogger(__name__)


def compute_optimal_k(
    items: Sequence[str],
    bias: float = 1.0,
    min_k: int = 3,
    max_k: Optional[int] = None,
) -> int:
    """Compute optimal number of items to keep using information saturation.

    Three-tier decision system:
      Tier 1 (fast path): trivial cases, near-duplicate detection
      Tier 2 (standard):  Kneedle on unique bigram coverage curve
      Tier 3 (validation): zlib compression ratio sanity check

    Args:
        items: Sequence of string items (in importance order).
        bias: Multiplier on knee point. >1 = keep more, <1 = keep fewer.
        min_k: Never return fewer than this.
        max_k: Never return more than this (None = no cap).

    Returns:
        Optimal number of items to keep.
    """
    n = len(items)
    effective_max = max_k if max_k is not None else n

    # Tier 1: Fast path
    if n <= 8:
        return n

    # Check for near-total redundancy
    unique_count = count_unique_simhash(items)
    if unique_count <= 3:
        k = max(min_k, unique_count)
        return min(k, effective_max)

    # Tier 2: Kneedle on unique bigram coverage
    curve = compute_unique_bigram_curve(items)
    knee = find_knee(curve)

    # Diversity ratio: fraction of items genuinely unique
    diversity_ratio = unique_count / n

    if knee is None:
        # No saturation found — each item adds new information
        # Scale keep-fraction continuously with diversity
        keep_fraction = 0.3 + 0.7 * diversity_ratio
        knee = max(min_k, int(n * keep_fraction))
    else:
        # Knee found, but if diversity is high, don't drop too much
        if diversity_ratio > 0.7:
            diversity_floor = max(min_k, int(n * (0.3 + 0.7 * diversity_ratio)))
            knee = max(knee, diversity_floor)

    # Apply bias multiplier
    k = max(min_k, int(knee * bias))
    k = min(k, effective_max)

    # Tier 3: Validate with zlib compression ratio
    k = _validate_with_zlib(items, k, effective_max)

    k = max(min_k, min(k, effective_max))

    logger.debug(
        f"adaptive_sizer: n={n} unique={unique_count} diversity={diversity_ratio:.2f} knee={knee} bias={bias:.1f} → k={k}"
    )
    return k


def find_knee(curve: List[int]) -> Optional[int]:
    """Find knee point in a monotonically increasing curve.

    Uses Kneedle algorithm: normalize to [0,1], compute difference
    from y=x diagonal, return index of maximum difference.

    Args:
        curve: List of cumulative values (e.g., unique bigram counts).

    Returns:
        Index of knee point, or None if no clear knee exists.
    """
    n = len(curve)
    if n < 3:
        return None

    # Normalize x and y to [0, 1]
    x_min, x_max = 0, n - 1
    y_min, y_max = curve[0], curve[-1]

    if y_max == y_min:
        # Flat curve — all items identical
        return 1

    x_range = x_max - x_min
    y_range = y_max - y_min

    # Compute difference from diagonal (y = x in normalized space)
    max_diff = -1.0
    knee_idx = None

    for i in range(n):
        x_norm = (i - x_min) / x_range
        y_norm = (curve[i] - y_min) / y_range
        diff = y_norm - x_norm
        if diff > max_diff:
            max_diff = diff
            knee_idx = i

    # Require meaningful deviation from diagonal
    if max_diff < 0.05:
        return None

    # Convert from 0-indexed to count
    return knee_idx + 1 if knee_idx is not None else None


def compute_unique_bigram_curve(items: Sequence[str]) -> List[int]:
    """Build cumulative unique bigram coverage curve.

    For each item (in order), extract word-level bigrams, add to running set,
    and record total unique count.

    Args:
        items: Sequence of string items in importance order.

    Returns:
        List where curve[k] = unique bigrams after seeing items[0:k+1].
    """
    seen_bigrams: set = set()
    curve: List[int] = []

    for item in items:
        words = item.lower().split()
        if len(words) < 2:
            # Single-word items: use word itself as unigram
            seen_bigrams.add((words[0] if words else "", ""))
        else:
            for j in range(len(words) - 1):
                seen_bigrams.add((words[j], words[j + 1]))
        curve.append(len(seen_bigrams))

    return curve


def _simhash(text: str) -> int:
    """Compute 64-bit SimHash fingerprint for text string.

    Uses character 4-grams hashed to 64-bit values, then aggregates
    via weighted bit voting.
    """
    v = [0] * 64
    text_lower = text.lower()

    # Character 4-grams
    for i in range(max(1, len(text_lower) - 3)):
        gram = text_lower[i : i + 4]
        h = int(hashlib.md5(gram.encode(), usedforsecurity=False).hexdigest()[:16], 16)
        for j in range(64):
            if h & (1 << j):
                v[j] += 1
            else:
                v[j] -= 1

    fingerprint = 0
    for j in range(64):
        if v[j] > 0:
            fingerprint |= 1 << j
    return fingerprint


def _hamming_distance(a: int, b: int) -> int:
    """Count differing bits between two 64-bit integers."""
    return bin(a ^ b).count("1")


def count_unique_simhash(items: Sequence[str], threshold: int = 3) -> int:
    """Count items with distinct content using SimHash.

    Groups items by SimHash fingerprint similarity (Hamming distance <= threshold).
    Returns number of distinct groups.

    Args:
        items: Sequence of string items.
        threshold: Max Hamming distance to consider items as duplicates.

    Returns:
        Number of unique content groups.
    """
    if not items:
        return 0

    # Compute fingerprints
    fingerprints = [_simhash(item) for item in items]

    # Greedy clustering: assign each to first matching cluster
    clusters: List[int] = []
    for fp in fingerprints:
        matched = False
        for rep in clusters:
            if _hamming_distance(fp, rep) <= threshold:
                matched = True
                break
        if not matched:
            clusters.append(fp)

    return len(clusters)


def _validate_with_zlib(
    items: Sequence[str],
    k: int,
    max_k: int,
    tolerance: float = 0.15,
) -> int:
    """Validate K using zlib compression ratio comparison.

    If compression ratio of selected subset differs significantly from
    full set, increase K.

    Args:
        items: All items.
        k: Currently proposed K.
        max_k: Maximum allowed K.
        tolerance: Max allowed ratio difference (default 15%).

    Returns:
        Adjusted K (may be increased if validation fails).
    """
    if k >= len(items) or k >= max_k:
        return k

    full_text = "\n".join(items).encode()
    subset_text = "\n".join(items[:k]).encode()

    # Skip validation for very small content
    if len(full_text) < 200:
        return k

    full_compressed = len(zlib.compress(full_text, level=1))
    subset_compressed = len(zlib.compress(subset_text, level=1))

    full_ratio = full_compressed / len(full_text) if full_text else 1.0
    subset_ratio = subset_compressed / len(subset_text) if subset_text else 1.0

    # If subset compresses much better than full, it's missing diverse content
    ratio_diff = abs(full_ratio - subset_ratio)

    if ratio_diff > tolerance:
        # Increase K by 20% to capture more diversity
        adjusted_k = min(int(k * 1.2), max_k)
        logger.debug(
            f"zlib validation: ratio_diff={ratio_diff:.3f} > {tolerance:.3f}, adjusting k={k} → {adjusted_k}"
        )
        return adjusted_k

    return k
