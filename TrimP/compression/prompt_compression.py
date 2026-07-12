"""
Prompt compression using templates and instruction rewriting.
Reduces system prompt size while preserving intent.
"""

from __future__ import annotations

import re


# Common verbose patterns in prompts
VERBOSE_PATTERNS = [
    # Politeness that can be shortened
    (r'(?i)please (always |make sure to )?', ''),
    (r'(?i)(i need you to|i want you to|you should|you must)', ''),
    (r'(?i)(it is important that|it is essential that|make sure that)', ''),
    
    # Redundant instructions
    (r'(?i)(be sure to|ensure that|remember to)', ''),
    (r'(?i)(you are|you\'re) (a|an) (helpful|useful|friendly) (assistant|ai|model)', 'Role:'),
    (r'(?i)your (job|task|role) is to', 'Role:'),
    
    # Output format verbosity
    (r'(?i)(always |please )?(format|structure|provide) (your|the) (output|response|answer) (as|in)', 'Output:'),
    (r'(?i)(make sure|ensure) (your|the) (output|response|answer) is', 'Output:'),
    (r'(?i)when (responding|answering), (always |please )?', ''),
]

# Role templates (compress common roles)
ROLE_TEMPLATES = {
    r'(?i)you are a kubernetes expert.*help.*debugging.*monitoring': 'Role: Kubernetes debugging expert.',
    r'(?i)you are a.*developer.*write.*code.*python': 'Role: Python developer.',
    r'(?i)you are a.*devops.*engineer.*infrastructure': 'Role: DevOps engineer.',
    r'(?i)you are a.*data.*scientist.*analyze.*data': 'Role: Data scientist.',
}


class PromptCompressor:
    """Compress system prompts using templates and instruction rewriting."""
    
    def __init__(self):
        self._verbose_patterns = [(re.compile(p, re.MULTILINE), r) for p, r in VERBOSE_PATTERNS]
        self._role_templates = [(re.compile(p), r) for p, r in ROLE_TEMPLATES.items()]
    
    def compress(self, prompt: str) -> tuple[str, int]:
        """
        Compress a system prompt.
        
        Returns:
            (compressed_prompt, tokens_saved)
        """
        if not prompt:
            return prompt, 0
        
        before_tokens = _estimate_tokens(prompt)
        result = prompt
        
        # Apply role templates first (biggest savings)
        for pattern, template in self._role_templates:
            if pattern.search(result):
                result = pattern.sub(template, result)
                break  # Only apply one role template
        
        # Remove verbose patterns
        for pattern, replacement in self._verbose_patterns:
            result = pattern.sub(replacement, result)
        
        # Compress output format instructions
        result = self._compress_output_format(result)
        
        # Clean up whitespace
        result = re.sub(r'\n{3,}', '\n\n', result)  # Max 2 newlines
        result = re.sub(r'[ \t]+', ' ', result)     # Single spaces
        result = result.strip()
        
        after_tokens = _estimate_tokens(result)
        return result, max(0, before_tokens - after_tokens)
    
    def _compress_output_format(self, text: str) -> str:
        """Compress output format instructions."""
        # Look for JSON output instructions
        if re.search(r'(?i)(format|structure).*output.*(json|javascript object notation)', text, re.DOTALL):
            text = re.sub(
                r'(?i)(format|provide|structure).*output.*(as|in).*(json|javascript object notation).*?(?=\n\n|\Z)',
                'Output: JSON.',
                text,
                flags=re.DOTALL
            )
        
        # Look for markdown output instructions
        if re.search(r'(?i)(format|structure).*output.*(markdown|md)', text, re.DOTALL):
            text = re.sub(
                r'(?i)(format|provide|structure).*output.*(as|in).*markdown.*?(?=\n\n|\Z)',
                'Output: Markdown.',
                text,
                flags=re.DOTALL
            )
        
        return text


def _estimate_tokens(text: str) -> int:
    """Estimate token count (4 chars per token)."""
    return max(1, len(text) // 4)
