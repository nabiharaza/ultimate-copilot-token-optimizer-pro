"""Conservative system-prompt deduplication.

Earlier versions used broad regex substitutions that could remove words such
as ``must`` and ``ensure`` or rewrite a large DOTALL output-format section.
Control prompts now receive only semantics-preserving whitespace cleanup and
exact duplicate-block removal. System compression remains opt-in at runtime.
"""

from __future__ import annotations

import re

from TrimP.tokenization import count_tokens


class PromptCompressor:
    """Deduplicate exact repeated prompt blocks without rewriting instructions."""

    def compress(self, prompt: str) -> tuple[str, int]:
        if not prompt:
            return prompt, 0
        before = count_tokens(prompt).tokens
        blocks = [block for block in re.split(r"\n{2,}", prompt) if block.strip()]
        seen: set[str] = set()
        result: list[str] = []
        for block in blocks:
            cleaned_lines: list[str] = []
            previous: str | None = None
            for line in block.splitlines():
                cleaned = line.rstrip()
                # Only consecutive byte-equivalent lines are removed. Similar
                # instructions with different modality remain distinct.
                if cleaned == previous:
                    continue
                cleaned_lines.append(cleaned)
                previous = cleaned
            cleaned_block = "\n".join(cleaned_lines).strip()
            fingerprint = cleaned_block
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            result.append(cleaned_block)
        compressed = "\n\n".join(result).strip()
        after = count_tokens(compressed).tokens
        if after >= before:
            return prompt, 0
        return compressed, before - after
