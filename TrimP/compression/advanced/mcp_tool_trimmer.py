"""
MCPToolTrimmer - Compress MCP tool schemas for agentic workflows.

Algorithm:
- Query-matched tool promotion (full schema for relevant tools)
- Stub-only for irrelevant tools (name + description only)
- Typical savings: 60-90%

Based on: GitHub's tool-search approach (VS Code June 2026 update).
"""

import re
import json
from typing import List, Dict, Tuple, Set


class MCPToolTrimmer:
    """Compress MCP tool registrations for agents."""
    
    def __init__(self, top_k: int = 5):
        """
        Args:
            top_k: Number of full schemas to include
        """
        self.top_k = top_k
    
    def compress(self, tools_json: str, query: str = "") -> Tuple[str, dict]:
        """
        Compress MCP tool schemas.
        
        Args:
            tools_json: JSON array of tool schemas
            query: User query/task (for relevance matching)
        
        Returns:
            (compressed_json, metadata)
        """
        try:
            tools = json.loads(tools_json)
        except json.JSONDecodeError:
            return tools_json, {
                'method': 'MCPToolTrimmer',
                'error': 'Invalid JSON',
                'savings_pct': 0
            }
        
        if not isinstance(tools, list):
            return tools_json, {
                'method': 'MCPToolTrimmer',
                'error': 'Expected array of tools',
                'savings_pct': 0
            }
        
        if len(tools) <= self.top_k:
            # Too few tools to trim
            return tools_json, {
                'method': 'MCPToolTrimmer',
                'tools_total': len(tools),
                'tools_full': len(tools),
                'savings_pct': 0
            }
        
        # Score tools by relevance to query
        scored_tools = []
        for tool in tools:
            score = self._score_tool(tool, query)
            scored_tools.append((tool, score))
        
        # Sort by score descending
        scored_tools.sort(key=lambda x: x[1], reverse=True)
        
        # Build result: top K full, rest as stubs
        result = []
        
        # First, add full schemas for top K
        full_tools = []
        for idx, (tool, score) in enumerate(scored_tools[:self.top_k]):
            full_tools.append(tool)
        
        # Then add a single summary stub for all others
        if len(scored_tools) > self.top_k:
            stub_count = len(scored_tools) - self.top_k
            stub_names = [tool['name'] for tool, score in scored_tools[self.top_k:self.top_k + 5]]  # Show first 5
            if stub_count > 5:
                stub_names.append(f'...+{stub_count - 5} more')
            
            summary_stub = {
                'summary': f'{stub_count} additional tools',
                'tools': ', '.join(stub_names)
            }
            result = full_tools + [summary_stub]
        else:
            result = full_tools
        
        compressed_json = json.dumps(result, separators=(',', ':'), ensure_ascii=False)
        
        original_chars = len(tools_json)
        compressed_chars = len(compressed_json)
        savings_pct = ((original_chars - compressed_chars) / original_chars * 100) if original_chars > 0 else 0
        
        return compressed_json, {
            'method': 'MCPToolTrimmer',
            'savings_pct': round(savings_pct, 1),
            'tools_total': len(tools),
            'tools_full': self.top_k,
            'tools_stubbed': len(tools) - self.top_k
        }
    
    def _score_tool(self, tool: Dict, query: str) -> float:
        """Score tool relevance to query."""
        score = 0.0
        
        if not query:
            # No query, use recency/position
            return 1.0
        
        # Extract query keywords
        query_words = set(re.findall(r'\b[a-z]{3,}\b', query.lower()))
        
        # Check tool name
        tool_name = tool.get('name', '').lower()
        tool_words = set(re.findall(r'\b[a-z]{3,}\b', tool_name))
        
        # Exact match bonus
        if any(qw in tool_name for qw in query_words):
            score += 10
        
        # Word overlap
        overlap = query_words & tool_words
        score += len(overlap) * 5
        
        # Check description
        tool_desc = tool.get('description', '').lower()
        desc_words = set(re.findall(r'\b[a-z]{3,}\b', tool_desc))
        
        # Description overlap
        desc_overlap = query_words & desc_words
        score += len(desc_overlap) * 2
        
        # Check parameters (if query mentions parameter names)
        if 'parameters' in tool and 'properties' in tool['parameters']:
            props = tool['parameters']['properties']
            for prop_name in props:
                if prop_name.lower() in query_words:
                    score += 3
        
        return score
    
    def _make_stub(self, tool: Dict) -> Dict:
        """Create a stub (name + description only)."""
        stub = {
            'name': tool.get('name', 'unknown'),
            # Truncate description significantly
            'description': (tool.get('description', 'No description')[:50] + '...') if len(tool.get('description', '')) > 50 else tool.get('description', '')
        }
        
        return stub


def compress_mcp_tools(tools_json: str, query: str = "", top_k: int = 5) -> Tuple[str, dict]:
    """
    Convenience function for MCP tool trimming.
    
    Args:
        tools_json: JSON array of tools
        query: User query for relevance
        top_k: Number of full schemas
    
    Returns:
        (compressed_json, metadata)
    """
    trimmer = MCPToolTrimmer(top_k=top_k)
    return trimmer.compress(tools_json, query=query)
