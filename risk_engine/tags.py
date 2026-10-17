"""Tags are the join key between the risk graph and a user's memory graph.
A finding carries tags (details["tags"]); memory stores the same tags on
mistakes and learned rules, so no cross-graph Cypher is needed."""
from __future__ import annotations

from . import config as C
from .models import Finding


def valid(tag: str) -> bool:
    return tag in C.TAG_VOCABULARY


def of(finding: Finding) -> list[str]:
    return [t for t in finding.details.get("tags", []) if valid(t)]


def collect(findings: list[Finding]) -> list[str]:
    seen: list[str] = []
    for f in findings:
        for t in of(f):
            if t not in seen:
                seen.append(t)
    return seen
