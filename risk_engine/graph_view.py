"""Read-only access to defi_risk. Every traversal goes through queries.py and
enforces the eligibility predicate in Cypher, so an ineligible edge can never
reach a rule, however the caller uses the results."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import config as C
from . import queries as Q
from .db import connect, ro
from .models import PathRec
from .util import pick, to_bool, to_epoch, to_float, to_int


@dataclass
class ProtocolFacts:
    key: str
    labels: list[str]
    props: dict
    name: str
    category: str | None
    tvl: float | None
    change_1d: float | None
    change_7d: float | None
    audits: int | None
    age_days: float | None
    chains: list[str] = field(default_factory=list)
    incidents: list[dict] = field(default_factory=list)
    pools: list[dict] = field(default_factory=list)


def norm_incident(props: dict) -> dict:
    return {
        "name": pick(props, C.PROPS["inc_name"]),
        "ts": to_epoch(pick(props, C.PROPS["inc_date"])),
        "amount": to_float(pick(props, C.PROPS["inc_amount"])),
        "classification": pick(props, C.PROPS["inc_class"]),
        "technique": pick(props, C.PROPS["inc_technique"]),
        "bridge": bool(to_bool(pick(props, C.PROPS["inc_bridge"]))),
    }


def norm_pool(props: dict) -> dict:
    return {
        "symbol": pick(props, C.PROPS["pool_symbol"]),
        "tvl": to_float(pick(props, C.PROPS["pool_tvl"])),
        "apy": to_float(pick(props, C.PROPS["pool_apy"])),
        "apy_base": to_float(pick(props, C.PROPS["pool_apy_base"])),
        "apy_reward": to_float(pick(props, C.PROPS["pool_apy_reward"])),
        "outlier": to_bool(pick(props, C.PROPS["pool_outlier"])),
        "il_risk": pick(props, C.PROPS["pool_il"]),
    }


class RiskGraph:
    def __init__(self, db=None, graph_name: str | None = None):
        self.db = db or connect()
        self.name = graph_name or C.RISK_GRAPH
        self.g = self.db.select_graph(self.name)

    def _ro(self, q: str, params: dict | None = None) -> list[list[Any]]:
        return ro(self.g, q, params)

    # ---- lookup -----------------------------------------------------------
    def resolve(self, key: str, label: str | None = None) -> dict | None:
        """Validate a name against the graph (never trust a model-supplied string)."""
        rows = self._ro(Q.resolve(label), {"k": key})
        if not rows:
            return None
        labels, props = rows[0]
        return {"key": key, "labels": labels, "props": dict(props)}

    def did_you_mean(self, q: str) -> list[dict]:
        return [{"key": r[0], "name": r[1]} for r in self._ro(Q.did_you_mean(), {"q": q})]

    # ---- facts ------------------------------------------------------------
    def protocol_facts(self, node: dict, now: float) -> ProtocolFacts:
        p = node["props"]
        k = node["key"]
        age = pick(p, C.PROPS["age_days"])
        if age is None:
            listed = to_epoch(pick(p, C.PROPS["listed_at"]))
            age = None if listed is None else max(0.0, (now - listed) / 86400.0)
        chains = [r[0] for r in self._ro(Q.Q_CHAINS, {"k": k}) if r[0] is not None]
        if not chains and isinstance(p.get("chains"), list):
            chains = [str(c) for c in p["chains"]]
        inc = [norm_incident(r[1]) for r in self._ro(Q.Q_INCIDENTS, {"keys": [k]})]
        pools = [norm_pool(r[0]) for r in self._ro(Q.Q_POOLS, {"k": k})]
        return ProtocolFacts(
            key=k,
            labels=node["labels"],
            props=p,
            name=str(pick(p, C.PROPS["name"]) or k),
            category=pick(p, C.PROPS["category"]),
            tvl=to_float(pick(p, C.PROPS["tvl"])),
            change_1d=to_float(pick(p, C.PROPS["change_1d"])),
            change_7d=to_float(pick(p, C.PROPS["change_7d"])),
            audits=to_int(pick(p, C.PROPS["audits"])),
            age_days=None if age is None else float(age),
            chains=chains,
            incidents=inc,
            pools=pools,
        )

    def incidents_for(self, keys: list[str]) -> dict[str, list[dict]]:
        out: dict[str, list[dict]] = {}
        if not keys:
            return out
        for k, props in self._ro(Q.Q_INCIDENTS, {"keys": list(keys)}):
            out.setdefault(k, []).append(norm_incident(props))
        return out

    # ---- eligible paths ---------------------------------------------------
    @staticmethod
    def _rec(r: list[Any]) -> PathRec:
        return PathRec(
            anchor=r[0], other=r[1], other_labels=r[2], other_props=dict(r[3] or {}),
            nodes=list(r[4]), rels=list(r[5]),
            strengths=[to_float(s) for s in r[6]], urls=list(r[7]),
        )

    def forward_paths(self, keys: list[str], max_hops: int | None = None) -> dict[str, list[PathRec]]:
        out: dict[str, list[PathRec]] = {k: [] for k in keys}
        if not keys:
            return out
        for r in self._ro(Q.forward_paths(max_hops or C.TH["MAX_HOPS"]), {"keys": list(keys)}):
            out.setdefault(r[0], []).append(self._rec(r))
        return out

    def reverse_paths(self, key: str, max_hops: int | None = None) -> list[PathRec]:
        return [self._rec(r) for r in self._ro(Q.reverse_paths(max_hops or C.TH["MAX_HOPS"]), {"k": key})]

    def all_eligible_edges(self) -> list[tuple[str, str]]:
        return [(r[0], r[1]) for r in self._ro(Q.Q_ALL_ELIGIBLE_EDGES)]

    # ---- diagnostics ------------------------------------------------------
    def diagnostics(self) -> dict:
        labels = [r[0] for r in self._ro(Q.Q_LABELS)]
        rel_types = [r[0] for r in self._ro(Q.Q_REL_TYPES)]
        node_props = {
            lab: {"count": self._ro(Q.q_label_count(lab))[0][0],
                  "property_keys": {r[0]: r[1] for r in self._ro(Q.q_label_props(lab))}}
            for lab in labels
        }
        edges = {}
        for t, total, eligible, rel_elig, verified, test in self._ro(Q.Q_EDGE_DIAG):
            edges[t] = {
                "total": total, "eligible": eligible, "risk_eligible_true": rel_elig,
                "verified_true": verified, "is_test_true": test,
                "carries_risk": t in C.DEPENDENCY_REL_TYPES,
                "property_keys": {r[0]: r[1] for r in self._ro(Q.q_rel_props(t))},
            }
        other = [t for t in rel_types if t not in edges]
        return {
            "graph": self.name, "labels": node_props, "dependency_edge_types": edges,
            "other_relationship_types": other, "eligibility_predicate": C.ELIGIBILITY_TEMPLATE,
            "eligible_dependency_edges": sum(
                v["eligible"] for t, v in edges.items() if t in C.DEPENDENCY_REL_TYPES),
        }
