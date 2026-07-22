"""
ArchitectureContextPacker - Compress design docs and architecture plans.

Algorithm:
- Extract component graph (services, modules, dependencies)
- Convert to adjacency list
- Interface-only mode (strip implementations)
- Typical savings: 60-80%

Based on: Software architecture visualization best practices.
"""

import re
from typing import List, Dict, Set, Tuple

_COMPONENT_NAME_PATTERN = re.compile(
    r'\b([A-Z][a-zA-Z]*(?:Service|Controller|Manager|Handler|Repository|Module|Component|API|Gateway))\b'
)
_QUOTED_SERVICE_PATTERN = re.compile(r'"([A-Za-z\-_]+(?:service|api|module))"', re.IGNORECASE)
_CODE_IDENTIFIER_PATTERN = re.compile(r'`([A-Za-z]+(?:Service|Controller|Manager|Handler))`')


class ArchitectureContextPacker:
    """Compress architecture documents to structured graphs."""
    
    def __init__(self, interfaces_only: bool = True):
        """
        Args:
            interfaces_only: Keep only interfaces, drop implementation details
        """
        self.interfaces_only = interfaces_only
    
    def compress(self, text: str) -> Tuple[str, dict]:
        """
        Compress architecture document to component graph.
        
        Returns:
            (compressed_graph, metadata)
        """
        # Extract components
        components = self._extract_components(text)
        
        # Extract relationships
        relationships = self._extract_relationships(text, components)
        
        # Extract interfaces
        interfaces = self._extract_interfaces(text, components) if self.interfaces_only else {}
        
        # Build compressed representation
        compressed = self._build_graph(components, relationships, interfaces)
        
        original_chars = len(text)
        compressed_chars = len(compressed)
        savings_pct = ((original_chars - compressed_chars) / original_chars * 100) if original_chars > 0 else 0
        
        return compressed, {
            'method': 'ArchitectureContextPacker',
            'savings_pct': round(savings_pct, 1),
            'components_found': len(components),
            'relationships_found': len(relationships),
            'interfaces_only': self.interfaces_only
        }
    
    def _extract_components(self, text: str) -> Set[str]:
        """Extract component/service names."""
        components = set()

        # Pattern 1: Service/Component names (capitalized or CamelCase)
        for match in _COMPONENT_NAME_PATTERN.finditer(text):
            components.add(match.group(1))

        # Pattern 2: Quoted service names
        for match in _QUOTED_SERVICE_PATTERN.finditer(text):
            components.add(match.group(1))

        # Pattern 3: Code identifiers
        for match in _CODE_IDENTIFIER_PATTERN.finditer(text):
            components.add(match.group(1))

        return components
    
    def _extract_relationships(self, text: str, components: Set[str]) -> List[Tuple[str, str, str]]:
        """Extract relationships between components."""
        relationships = []
        
        # Pattern: "A calls B", "A depends on B", "A → B"
        relationship_words = ['calls', 'depends on', 'uses', 'connects to', 'sends to', 'queries', 'invokes']
        
        for comp_a in components:
            for comp_b in components:
                if comp_a == comp_b:
                    continue
                
                # Check for explicit relationships
                for rel_word in relationship_words:
                    pattern = rf'\b{comp_a}\b[^.!?]*\b{rel_word}\b[^.!?]*\b{comp_b}\b'
                    if re.search(pattern, text, re.IGNORECASE):
                        relationships.append((comp_a, rel_word, comp_b))
                        break
                
                # Check for arrow notation
                arrow_pattern = rf'\b{re.escape(comp_a)}\b\s*[→\->]+\s*\b{re.escape(comp_b)}\b'
                if re.search(arrow_pattern, text):
                    relationships.append((comp_a, '→', comp_b))
        
        return relationships
    
    def _extract_interfaces(self, text: str, components: Set[str]) -> Dict[str, List[str]]:
        """Extract public interfaces/methods for each component."""
        interfaces = {}
        
        for comp in components:
            methods = []
            
            # Pattern: method names in context of component
            # Look for lines mentioning the component and method-like words
            comp_context = []
            for line in text.split('\n'):
                if comp.lower() in line.lower():
                    comp_context.append(line)
            
            context_text = ' '.join(comp_context)
            
            # Extract method names (camelCase or snake_case)
            for match in re.finditer(r'\b([a-z][a-zA-Z0-9_]*)\s*\(', context_text):
                method = match.group(1)
                if method not in ['if', 'while', 'for', 'return']:  # Skip keywords
                    methods.append(method)
            
            if methods:
                interfaces[comp] = list(set(methods))[:5]  # Top 5 unique methods
        
        return interfaces
    
    def _build_graph(self, components: Set[str], 
                    relationships: List[Tuple[str, str, str]],
                    interfaces: Dict[str, List[str]]) -> str:
        """Build compressed graph representation."""
        lines = ["# Architecture Graph\n"]
        
        # Components section
        lines.append("## Components")
        for comp in sorted(components):
            if comp in interfaces and interfaces[comp]:
                methods_str = ', '.join(interfaces[comp][:3])
                lines.append(f"- {comp}: {methods_str}")
            else:
                lines.append(f"- {comp}")
        
        # Relationships section
        if relationships:
            lines.append("\n## Dependencies")
            for source, rel, target in relationships:
                lines.append(f"- {source} {rel} {target}")
        
        return '\n'.join(lines)


def compress_architecture(text: str, interfaces_only: bool = True) -> Tuple[str, dict]:
    """
    Convenience function for architecture compression.
    
    Args:
        text: Architecture document
        interfaces_only: Keep only interfaces
    
    Returns:
        (compressed_graph, metadata)
    """
    packer = ArchitectureContextPacker(interfaces_only=interfaces_only)
    return packer.compress(text)
