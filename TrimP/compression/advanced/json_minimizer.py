"""
JSONMinimizer - Aggressive JSON compression.

Algorithm:
- Whitelist important keys, drop rest
- Depth cap (prune deep nested objects)
- Array sampling (keep first/last + sample middle)
- Null/empty value removal
- Compact serialization
- Typical savings: 60-90%

Based on: API payload optimization best practices.
"""

import json
from typing import Any, Dict, List, Set, Tuple


class JSONMinimizer:
    """Compress JSON payloads while preserving critical data."""
    
    def __init__(self, 
                 whitelist_keys: Set[str] = None,
                 max_depth: int = 4,
                 max_array_items: int = 10):
        """
        Args:
            whitelist_keys: Keys to always preserve (None = smart detection)
            max_depth: Maximum nesting depth to preserve
            max_array_items: Max items to keep in arrays
        """
        self.whitelist_keys = whitelist_keys or {
            # Common important keys
            'id', 'name', 'type', 'status', 'error', 'message', 'code',
            'timestamp', 'created_at', 'updated_at',
            'user', 'username', 'email',
            'data', 'result', 'results', 'items',
            'key', 'value', 'title', 'description'
        }
        self.max_depth = max_depth
        self.max_array_items = max_array_items
    
    def compress(self, text: str) -> Tuple[str, dict]:
        """
        Compress JSON text.
        
        Returns:
            (compressed_json_text, metadata)
        """
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Not valid JSON, return as-is
            return text, {
                'method': 'JSONMinimizer',
                'error': 'Invalid JSON',
                'savings_pct': 0
            }
        
        # Compress the data structure
        compressed_data, stats = self._compress_value(data, depth=0)
        
        # Serialize compactly (no whitespace)
        compressed_text = json.dumps(compressed_data, separators=(',', ':'), ensure_ascii=False)
        
        original_chars = len(text)
        compressed_chars = len(compressed_text)
        savings_pct = ((original_chars - compressed_chars) / original_chars * 100) if original_chars > 0 else 0
        
        return compressed_text, {
            'method': 'JSONMinimizer',
            'savings_pct': round(savings_pct, 1),
            'keys_dropped': stats['keys_dropped'],
            'arrays_sampled': stats['arrays_sampled'],
            'nulls_dropped': stats['nulls_dropped']
        }
    
    def _compress_value(self, value: Any, depth: int) -> Tuple[Any, Dict]:
        """Recursively compress a JSON value."""
        stats = {'keys_dropped': 0, 'arrays_sampled': 0, 'nulls_dropped': 0}
        
        # Depth limit reached
        if depth > self.max_depth:
            return '...', stats
        
        # Handle different types
        if isinstance(value, dict):
            return self._compress_dict(value, depth, stats)
        elif isinstance(value, list):
            return self._compress_array(value, depth, stats)
        elif value is None:
            stats['nulls_dropped'] += 1
            return None, stats
        else:
            # Primitive: keep as-is
            return value, stats
    
    def _compress_dict(self, obj: Dict, depth: int, stats: Dict) -> Tuple[Dict, Dict]:
        """Compress a dictionary."""
        result = {}
        
        for key, value in obj.items():
            # More aggressive whitelist filtering
            key_lower = key.lower()
            
            # Always keep critical keys
            if key_lower in {'id', 'name', 'type', 'error', 'message'}:
                pass  # Always keep
            elif key_lower not in self.whitelist_keys:
                # Not whitelisted, apply strict filtering
                if depth > 1 or not self._is_important_value(value):
                    # Drop non-important or deeply nested
                    stats['keys_dropped'] += 1
                    continue
            
            # Recursively compress value
            compressed_value, child_stats = self._compress_value(value, depth + 1)
            
            # Merge stats
            for k in stats:
                stats[k] += child_stats.get(k, 0)
            
            # Skip null values
            if compressed_value is None:
                continue
            
            result[key] = compressed_value
        
        return result, stats
    
    def _compress_array(self, arr: List, depth: int, stats: Dict) -> Tuple[List, Dict]:
        """Compress an array using sampling."""
        if len(arr) <= self.max_array_items:
            # Small array, compress each item
            result = []
            for item in arr:
                compressed_item, child_stats = self._compress_value(item, depth + 1)
                for k in stats:
                    stats[k] += child_stats.get(k, 0)
                if compressed_item is not None:
                    result.append(compressed_item)
            return result, stats
        
        # Large array: sample first, last, and middle
        stats['arrays_sampled'] += 1
        
        # Take first 3, last 3, and a few from middle
        sample_size = self.max_array_items - 1  # -1 for ellipsis marker
        first_n = min(3, sample_size // 2)
        last_n = min(3, sample_size // 2)
        mid_n = sample_size - first_n - last_n
        
        sampled = []
        
        # First items
        for item in arr[:first_n]:
            compressed_item, child_stats = self._compress_value(item, depth + 1)
            for k in stats:
                stats[k] += child_stats.get(k, 0)
            if compressed_item is not None:
                sampled.append(compressed_item)
        
        # Middle items (evenly spaced)
        if mid_n > 0 and len(arr) > first_n + last_n:
            mid_start = first_n
            mid_end = len(arr) - last_n
            mid_indices = [mid_start + i * (mid_end - mid_start) // (mid_n + 1) for i in range(1, mid_n + 1)]
            for idx in mid_indices:
                compressed_item, child_stats = self._compress_value(arr[idx], depth + 1)
                for k in stats:
                    stats[k] += child_stats.get(k, 0)
                if compressed_item is not None:
                    sampled.append(compressed_item)
        
        # Ellipsis marker
        sampled.append(f'...({len(arr) - sample_size} items omitted)')
        
        # Last items
        for item in arr[-last_n:]:
            compressed_item, child_stats = self._compress_value(item, depth + 1)
            for k in stats:
                stats[k] += child_stats.get(k, 0)
            if compressed_item is not None:
                sampled.append(compressed_item)
        
        return sampled, stats
    
    def _is_important_value(self, value: Any) -> bool:
        """Determine if a value looks important."""
        if isinstance(value, (dict, list)):
            # Non-empty structured data is important
            return len(value) > 0
        if isinstance(value, str):
            # Non-empty strings are important
            return len(value.strip()) > 0
        if isinstance(value, (int, float)):
            # Non-zero numbers are important
            return value != 0
        return False


def compress_json(text: str, 
                  whitelist_keys: Set[str] = None,
                  max_depth: int = 4,
                  max_array_items: int = 10) -> Tuple[str, dict]:
    """
    Convenience function for JSON minimization.
    
    Args:
        text: JSON string
        whitelist_keys: Keys to preserve
        max_depth: Max nesting depth
        max_array_items: Max array size
    
    Returns:
        (compressed_json, metadata)
    """
    minimizer = JSONMinimizer(
        whitelist_keys=whitelist_keys,
        max_depth=max_depth,
        max_array_items=max_array_items
    )
    return minimizer.compress(text)
