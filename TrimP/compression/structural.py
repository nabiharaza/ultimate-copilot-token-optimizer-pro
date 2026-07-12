"""
Structural auditor — configs, skills, MCP, memory scoring.
Each source scored and ranked by token cost.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class SourceAudit:
    name: str
    path: str
    char_count: int
    token_est: int
    issues: list[str]
    score: float  # 0.0–1.0 (higher = more efficient)
    grade: str


@dataclass
class StructuralAuditor:
    """Audit structural context sources: MEMORY.md, config, skills, MCP."""

    search_paths: list[str] = field(default_factory=lambda: [
        str(Path.home() / ".copilot"),
        str(Path.home() / ".github"),
        ".",
        ".github",
    ])

    def audit_all(self) -> list[SourceAudit]:
        results: list[SourceAudit] = []
        targets = [
            ("MEMORY.md", self._audit_memory),
            (".copilot/config.yml", self._audit_config),
            (".copilot/skills.yml", self._audit_skills),
            ("mcp.json", self._audit_mcp),
            (".github/copilot-instructions.md", self._audit_instructions),
        ]

        for name, auditor in targets:
            for base in self.search_paths:
                path = Path(base) / name
                if path.exists():
                    try:
                        content = path.read_text(encoding="utf-8", errors="replace")
                        audit = auditor(content, str(path))
                        results.append(audit)
                    except Exception:
                        pass
                    break

        results.sort(key=lambda a: a.token_est, reverse=True)
        return results

    def _audit_memory(self, content: str, path: str) -> SourceAudit:
        issues = []
        score = 1.0
        lines = content.splitlines()

        if len(content) > 10_000:
            issues.append(f"MEMORY.md is very large ({len(content):,} chars) — consider pruning")
            score -= 0.3

        # Look for stale/redundant sections
        stale_markers = re.findall(r"(?i)(TODO:|FIXME:|OUTDATED:|OLD:)", content)
        if stale_markers:
            issues.append(f"{len(stale_markers)} stale markers found")
            score -= 0.1

        # Duplicate headings
        headings = [l for l in lines if l.startswith("#")]
        if len(set(headings)) < len(headings):
            issues.append("Duplicate headings detected")
            score -= 0.1

        # Verbose filler
        filler = re.findall(r"(?i)\b(please note|it is important to|make sure to)\b", content)
        if len(filler) > 3:
            issues.append(f"{len(filler)} verbose filler phrases")
            score -= 0.05 * len(filler)

        return _make_audit("MEMORY.md", path, content, max(0.0, score), issues)

    def _audit_config(self, content: str, path: str) -> SourceAudit:
        issues = []
        score = 1.0
        if len(content) > 5_000:
            issues.append("Config file is large — check for commented-out sections")
            score -= 0.2
        return _make_audit("config", path, content, score, issues)

    def _audit_skills(self, content: str, path: str) -> SourceAudit:
        issues = []
        score = 1.0
        skill_count = content.count("- name:") + content.count("name:")
        if skill_count > 20:
            issues.append(f"{skill_count} skills defined — unused skills waste context")
            score -= 0.15
        return _make_audit("skills", path, content, score, issues)

    def _audit_mcp(self, content: str, path: str) -> SourceAudit:
        issues = []
        score = 1.0
        try:
            data = json.loads(content)
            servers = data.get("mcpServers", {})
            if len(servers) > 5:
                issues.append(f"{len(servers)} MCP servers — each adds schema overhead")
                score -= 0.1 * (len(servers) - 5)
        except Exception:
            issues.append("Could not parse mcp.json")
            score -= 0.1
        return _make_audit("mcp.json", path, content, max(0.0, score), issues)

    def _audit_instructions(self, content: str, path: str) -> SourceAudit:
        issues = []
        score = 1.0
        if len(content) > 8_000:
            issues.append("copilot-instructions.md is large — every turn pays this cost")
            score -= 0.25
        neg_instructions = re.findall(r"(?i)\bdo not\b|\bnever\b|\bavoid\b", content)
        if len(neg_instructions) > 15:
            issues.append(f"{len(neg_instructions)} negative instructions — consider consolidating")
            score -= 0.1
        return _make_audit("instructions", path, content, max(0.0, score), issues)


def _make_audit(name: str, path: str, content: str, score: float, issues: list[str]) -> SourceAudit:
    token_est = max(1, len(content) // 4)
    grade = _grade(score)
    return SourceAudit(
        name=name, path=path, char_count=len(content),
        token_est=token_est, issues=issues, score=score, grade=grade,
    )


def _grade(score: float) -> str:
    if score >= 0.9:
        return "S"
    if score >= 0.8:
        return "A"
    if score >= 0.65:
        return "B"
    if score >= 0.5:
        return "C"
    if score >= 0.3:
        return "D"
    return "F"
