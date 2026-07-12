"""Tests for Headroom algorithm integrations."""

import pytest
from TrimP.compression.headroom import (
    BM25Scorer,
    compute_optimal_k,
    find_knee,
    detect_volatile_content,
    get_cache_alignment_score,
)


def test_bm25_exact_match():
    """Test BM25 scores term matches correctly."""
    scorer = BM25Scorer()
    doc = "Database connection failed with error code 500 timeout"
    query = "database error"
    
    score, matched = scorer.score(doc, query)
    assert score > 0, f"Expected non-zero score for term match, got {score}"
    assert len(matched) >= 1, f"Expected matched terms, got {matched}"
    assert "database" in matched or "error" in matched, f"Expected 'database' or 'error' in {matched}"


def test_bm25_batch_scoring():
    """Test BM25 batch scoring ranks items correctly."""
    scorer = BM25Scorer()
    items = [
        "Error: connection timeout",
        "Success: data saved",
        "Error: database unavailable",
        "Info: starting process",
    ]
    query = "error database"
    
    results = scorer.score_batch(items, query)
    scores = [score for score, _ in results]
    
    # Item 2 ("Error: database unavailable") should rank highest
    assert scores[2] > scores[0], "Database error should score higher than timeout"
    assert scores[2] > scores[1], "Error should score higher than success"


def test_adaptive_sizer_basic():
    """Test adaptive sizing finds reasonable K."""
    items = ["line1", "line2", "line3", "line4 similar", "line5 similar"]
    k = compute_optimal_k(items, bias=1.0, min_k=1)
    
    assert 1 <= k <= len(items), f"K should be between 1 and {len(items)}, got {k}"
    assert k >= 1, "K should be at least min_k"


def test_adaptive_sizer_duplicates():
    """Test adaptive sizing detects duplicates."""
    items = ["same"] * 10
    k = compute_optimal_k(items, bias=1.0, min_k=1)
    
    # Should recognize all are duplicates and keep very few
    assert k <= 3, f"Expected K <= 3 for duplicates, got {k}"


def test_adaptive_sizer_unique():
    """Test adaptive sizing keeps unique items."""
    items = [f"unique content {i} with different information" for i in range(20)]
    k = compute_optimal_k(items, bias=1.0, min_k=3)
    
    # Should keep most/all since all are unique
    assert k >= 10, f"Expected K >= 10 for unique items, got {k}"


def test_find_knee_basic():
    """Test knee detection on clear curve."""
    # Curve with clear knee at index 3
    curve = [1, 3, 7, 10, 11, 12, 12]  # Steep rise then plateau
    knee = find_knee(curve)
    
    assert knee is not None, "Should find a knee"
    assert 2 <= knee <= 5, f"Expected knee around 3-4, got {knee}"


def test_find_knee_flat():
    """Test knee detection on flat curve."""
    curve = [5, 5, 5, 5, 5]
    knee = find_knee(curve)
    
    # Flat curve should return early knee or None
    assert knee is None or knee == 1, f"Expected None or 1 for flat curve, got {knee}"


def test_cache_detector_uuid():
    """Test cache detector finds UUIDs."""
    text = "User ID: 550e8400-e29b-41d4-a716-446655440000"
    findings = detect_volatile_content(text)
    
    assert len(findings) > 0, "Should detect UUID"
    assert findings[0].label == "uuid", f"Expected uuid label, got {findings[0].label}"


def test_cache_detector_timestamp():
    """Test cache detector finds ISO 8601 timestamps."""
    text = "Created at 2024-01-15T10:30:00Z"
    findings = detect_volatile_content(text)
    
    assert len(findings) > 0, "Should detect timestamp"
    assert findings[0].label == "iso8601", f"Expected iso8601 label, got {findings[0].label}"


def test_cache_detector_jwt():
    """Test cache detector finds JWT tokens."""
    # Valid JWT structure (header.payload.signature)
    jwt = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
    text = f"Authorization: Bearer {jwt}"
    findings = detect_volatile_content(text)
    
    assert len(findings) > 0, "Should detect JWT"
    assert any(f.label == "jwt" for f in findings), f"Expected jwt in findings, got {[f.label for f in findings]}"


def test_cache_detector_hex_hash():
    """Test cache detector finds hex hashes."""
    text = "File hash: 5d41402abc4b2a76b9719d911017c592"  # MD5
    findings = detect_volatile_content(text)
    
    assert len(findings) > 0, "Should detect hash"
    assert findings[0].label == "hex_hash", f"Expected hex_hash label, got {findings[0].label}"


def test_cache_alignment_score():
    """Test cache alignment scoring."""
    # Clean text
    clean = "This is a stable prompt with no volatile content."
    score_clean = get_cache_alignment_score(clean)
    assert score_clean == 100.0, f"Expected 100 for clean text, got {score_clean}"
    
    # Text with volatile content
    volatile = "User: 550e8400-e29b-41d4-a716-446655440000 at 2024-01-15T10:30:00Z"
    score_volatile = get_cache_alignment_score(volatile)
    assert score_volatile < 100.0, f"Expected < 100 for volatile text, got {score_volatile}"
    assert score_volatile >= 0.0, "Score should not go negative"


def test_headroom_integration_quality():
    """Test that Headroom algorithms maintain quality."""
    # BM25 should find relevant matches
    scorer = BM25Scorer()
    relevant = "Database connection failed with error code 500"
    irrelevant = "User logged in successfully"
    query = "database error"
    
    score_rel, _ = scorer.score(relevant, query)
    score_irrel, _ = scorer.score(irrelevant, query)
    
    assert score_rel > score_irrel, "Relevant item should score higher than irrelevant"
    
    # Adaptive sizer should be intelligent
    diverse = [f"Item {i}: {' '.join(['word' + str(j) for j in range(i, i+5)])}" for i in range(50)]
    k_diverse = compute_optimal_k(diverse, bias=1.0, min_k=5)
    
    duplicates = ["same text"] * 50
    k_dupe = compute_optimal_k(duplicates, bias=1.0, min_k=1)
    
    assert k_diverse > k_dupe * 2, "Should keep more diverse items than duplicates"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
