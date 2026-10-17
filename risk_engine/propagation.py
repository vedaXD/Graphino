"""Bounded risk propagation and exposure over ELIGIBLE edges only.

Shock semantics: (A)-[:DEPENDS_ON]->(B) means A depends on B, so a failure at B
reaches A by walking incoming edges. Impact is an ESTIMATE: severity multiplied
by edge strengths along the best path (strengths are modelling judgments).
Synthetic shocks are computed in memory and never written to the graph.
"""
from __future__ import annotations

from collections import defaultdict

from . import config as C
from .graph_view import RiskGraph
from .models import PathRec
from .util import clamp_float, clamp_int


def path_strength(rec: PathRec) -> float:
    s = 1.0
    for rel, st in zip(rec.rels, rec.strengths):
        s *= st if st is not None else C.DEFAULT_STRENGTH.get(rel, 0.5)
    return s


def best_paths(recs: list[PathRec]) -> dict[str, PathRec]:
    """One path per `other` node: fewest hops, then strongest."""
    best: dict[str, PathRec] = {}
    for r in recs:
        cur = best.get(r.other)
        if cur is None or (r.hops, -path_strength(r)) < (cur.hops, -path_strength(cur)):
            best[r.other] = r
    return best


# ---- shock simulation --------------------------------------------------------
def simulate_shock(rg: RiskGraph, node_key: str, severity: float = 1.0, max_hops: int = 3,
                   positions: list[dict] | None = None) -> dict:
    """If `node_key` fails with `severity` (0..1), who is affected and by how much?"""
    severity = clamp_float(severity, 0.0, 1.0, 1.0)
    max_hops = clamp_int(max_hops, 1, 4, C.TH["MAX_HOPS"])
    node = rg.resolve(node_key)
    if node is None:
        return {"outcome": "unknown_node", "node": node_key, "did_you_mean": rg.did_you_mean(node_key),
                "note": "Not in the graph. Absence of a node means not modelled, not safe."}
    best = best_paths(rg.reverse_paths(node_key, max_hops))
    affected = []
    for other, rec in best.items():
        if other == node_key:
            continue
        impact = severity * path_strength(rec)
        affected.append({
            "node": other, "labels": rec.other_labels, "hops": rec.hops,
            "impact_fraction": round(impact, 4), "path": rec.nodes, "rels": rec.rels,
            "evidence": rec.edge_evidence(),
        })
    affected.sort(key=lambda a: (-a["impact_fraction"], a["hops"], a["node"]))
    by_key = {a["node"]: a for a in affected}
    hit = []
    for p in positions or []:
        a = by_key.get(p["protocol_id"])
        if a:
            hit.append({**a, "amount_usd": p["amount_usd"],
                        "estimated_loss_usd": round(p["amount_usd"] * a["impact_fraction"], 2)})
    return {
        "outcome": "no_modelled_dependents" if not affected else "ok",
        "node": node_key, "labels": node["labels"], "severity": severity, "max_hops": max_hops,
        "affected": affected, "affected_positions": hit,
        "estimated_total_loss_usd": round(sum(h["estimated_loss_usd"] for h in hit), 2),
        "note": ("Impact is an estimate from edge-strength weights. An empty result means "
                 "no verified dependents are modelled, not that nothing depends on it."),
    }


# ---- portfolio exposure ------------------------------------------------------
def build_exposure(fwd: dict[str, list[PathRec]], amounts: dict[str, float], capital_usd: float,
                   min_protocols: int = 2) -> list[dict]:
    """Dependency nodes shared by >= min_protocols holdings, with capital share."""
    by_dep: dict[str, dict[str, PathRec]] = defaultdict(dict)
    labels: dict[str, list[str]] = {}
    for proto, recs in fwd.items():
        if proto not in amounts:
            continue
        for dep, rec in best_paths(recs).items():
            if dep == proto:
                continue
            by_dep[dep][proto] = rec
            labels[dep] = rec.other_labels
    rows = []
    for dep, per in by_dep.items():
        if len(per) < min_protocols:
            continue
        usd = sum(amounts[p] for p in per)
        rows.append({
            "dependency": dep, "labels": labels[dep], "protocols": sorted(per),
            "usd": round(usd, 2),
            "share_pct": round(100.0 * usd / capital_usd, 2) if capital_usd else 0.0,
            "paths": {p: r.nodes for p, r in per.items()},
            "evidence": [e for r in per.values() for e in r.edge_evidence()],
        })
    rows.sort(key=lambda r: (-r["share_pct"], r["dependency"]))
    return rows


def portfolio_exposure(rg: RiskGraph, positions: list[dict], capital_usd: float | None = None,
                       max_hops: int = 3) -> dict:
    amounts: dict[str, float] = defaultdict(float)
    for p in positions:
        amounts[p["protocol_id"]] += float(p["amount_usd"])
    capital = capital_usd or sum(amounts.values())
    fwd = rg.forward_paths(list(amounts), clamp_int(max_hops, 1, 4, C.TH["MAX_HOPS"]))
    modelled = {k: bool(v) for k, v in fwd.items()}
    return {
        "capital_usd": capital, "shared_dependencies": build_exposure(fwd, dict(amounts), capital),
        "holdings_without_modelled_dependencies": sorted(k for k, ok in modelled.items() if not ok),
        "note": "Only verified, risk-eligible edges are counted. Missing edges mean not modelled.",
    }


# ---- systemic importance -----------------------------------------------------
def pagerank(edges: list[tuple[str, str]], damping: float = 0.85, iters: int = 60) -> dict[str, float]:
    """PageRank over the ELIGIBLE dependency graph (rank flows to dependencies).
    Computed here, not with algo.pageRank, because native algorithm filters work
    by label/relationship type, not by edge property, so they would count
    ineligible edges."""
    nodes = sorted({n for e in edges for n in e})
    if not nodes:
        return {}
    out = defaultdict(list)
    for a, b in edges:
        out[a].append(b)
    n = len(nodes)
    pr = {k: 1.0 / n for k in nodes}
    for _ in range(iters):
        nxt = {k: (1.0 - damping) / n for k in nodes}
        dangling = sum(pr[k] for k in nodes if not out[k])
        for k in nodes:
            share = damping * pr[k] / len(out[k]) if out[k] else 0.0
            for b in out[k]:
                nxt[b] += share
            nxt[k] += damping * dangling / n
        pr = nxt
    return pr


def systemic_importance(rg: RiskGraph, node_key: str, max_hops: int = 3) -> dict:
    node = rg.resolve(node_key)
    if node is None:
        return {"outcome": "unknown_node", "node": node_key, "did_you_mean": rg.did_you_mean(node_key)}
    best = best_paths(rg.reverse_paths(node_key, clamp_int(max_hops, 1, 4, C.TH["MAX_HOPS"])))
    best.pop(node_key, None)
    pr = pagerank(rg.all_eligible_edges())
    ranked = sorted(pr, key=lambda k: -pr[k])
    return {
        "outcome": "ok", "node": node_key, "labels": node["labels"],
        "direct_dependents": sorted(k for k, r in best.items() if r.hops == 1),
        "transitive_dependents": sorted(k for k, r in best.items() if r.hops > 1),
        "dependents_count": len(best),
        "pagerank": round(pr.get(node_key, 0.0), 5),
        "pagerank_rank": (ranked.index(node_key) + 1) if node_key in pr else None,
        "ranked_nodes": len(ranked),
        "note": "Computed over verified, risk-eligible edges only.",
    }
