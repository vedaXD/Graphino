"""Contracts: Finding / Verdict shapes match IMPLEMENTATION_PLAN.md section 3.4,
plus additive fields (action, cap_usd, details) the gate and UI need."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .util import short_hash


@dataclass
class Position:
    protocol_id: str
    amount_usd: float
    chain: str | None = None

    @classmethod
    def from_any(cls, v: Any) -> "Position":
        if isinstance(v, Position):
            return v
        return cls(str(v["protocol_id"]), float(v["amount_usd"]), v.get("chain"))


@dataclass
class Proposal(Position):
    @classmethod
    def from_any(cls, v: Any) -> "Proposal":
        if isinstance(v, Proposal):
            return v
        return cls(str(v["protocol_id"]), float(v["amount_usd"]), v.get("chain"))

    def key(self) -> dict:
        return {"protocol_id": self.protocol_id, "amount_usd": self.amount_usd, "chain": self.chain}


@dataclass
class Finding:
    rule: str
    severity: str  # high | medium | low | info
    summary: str
    path: list[str]
    subject: str
    action: str = "none"  # none | warn | cap | block
    cap_usd: float | None = None
    evidence: list[dict] = field(default_factory=list)
    memory_ref: dict | None = None
    details: dict = field(default_factory=dict)

    @property
    def id(self) -> str:
        return "F-" + short_hash(self.rule, self.subject, ">".join(self.path))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "rule": self.rule,
            "severity": self.severity,
            "summary": self.summary,
            "path": self.path,
            "action": self.action,
            "cap_usd": None if self.cap_usd is None else round(self.cap_usd, 2),
            "evidence": self.evidence,
            "memory_ref": self.memory_ref,
            "details": self.details,
        }


@dataclass
class PathRec:
    """One eligible dependency path as returned by the graph (the explanation comes
    from nodes(path) in the same query that found it, not from the model).

    `nodes` always runs dependent -> dependency. `anchor` is the node you asked
    about (forward query: the protocol; reverse query: the shocked node) and
    `other` is the node found at the far end."""
    anchor: str
    other: str
    other_labels: list[str]
    other_props: dict
    nodes: list[str]
    rels: list[str]
    strengths: list[float | None]
    urls: list[str | None]

    @property
    def hops(self) -> int:
        return len(self.rels)

    def edge_evidence(self) -> list[dict]:
        return [{"kind": "edge", "rel": r, "source_url": u} for r, u in zip(self.rels, self.urls) if u]
