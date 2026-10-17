"""assess_proposal: facts + eligible multi-hop paths -> deterministic rules -> verdict."""
from __future__ import annotations

import time
from collections import defaultdict

from . import config as C
from . import rules as R
from . import tags as T
from .evidence import EvidenceIndex
from .graph_view import RiskGraph
from .models import Finding, Position, Proposal
from .propagation import best_paths
from .util import clamp_int

_SEV = {"high": 0, "medium": 1, "low": 2, "info": 3}


def _unknown(proposal: Proposal, rg: RiskGraph) -> dict:
    return {
        "outcome": "BLOCK", "reason": "unknown_protocol", "proposal": proposal.key(),
        "allowed_amount_usd": 0.0, "findings": [],
        "message": (f"'{proposal.protocol_id}' is not in the risk graph, so it cannot be assessed. "
                    "Not modelled is not the same as safe."),
        "did_you_mean": rg.did_you_mean(proposal.protocol_id),
        "coverage": {"modelled": False}, "rules_version": C.RULES_VERSION, "disclaimer": C.DISCLAIMER,
    }


def assess_proposal(proposal, positions=None, prefs=None, memory_rules=None, mistakes=None,
                    capital_usd=None, synthetic_shocks=None, rg: RiskGraph | None = None,
                    evidence: EvidenceIndex | None = None, now: float | None = None,
                    max_hops: int | None = None) -> dict:
    rg = rg or RiskGraph()
    now = now or time.time()
    prop = Proposal.from_any(proposal)
    prefs, memory_rules, mistakes = prefs or {}, memory_rules or [], mistakes or []
    hops = clamp_int(max_hops, 1, 4, C.TH["MAX_HOPS"])
    holdings = [Position.from_any(p) for p in (positions or [])]

    node = rg.resolve(prop.protocol_id, "Protocol")
    if node is None:
        return _unknown(prop, rg)

    amounts: dict[str, float] = defaultdict(float)
    for h in holdings:
        amounts[h.protocol_id] += h.amount_usd
    capital = float(capital_usd) if capital_usd else sum(amounts.values()) + prop.amount_usd
    mult = C.TOLERANCE_MULT.get(str(prefs.get("risk_tolerance", "moderate")).lower(), 1.0)

    facts = rg.protocol_facts(node, now)
    fwd = rg.forward_paths(sorted(set(amounts) | {prop.protocol_id}), hops)
    paths = best_paths(fwd.get(prop.protocol_id, []))
    paths.pop(prop.protocol_id, None)
    dep_inc = rg.incidents_for(list(paths))

    ctx = R.Ctx(prop, facts, dict(amounts), capital, mult, now, paths, fwd, dep_inc,
                prefs, memory_rules, mistakes, synthetic_shocks or [])

    findings: list[Finding] = []
    for rule in (R.r9_coverage, R.r1_concentration, R.r2_young_unaudited, R.r3_incidents,
                 R.r4_peg, R.r5_controller, R.r6_market, R.r8_prefs, R.s1_synthetic):
        findings += rule(ctx)
    findings += R.r7_memory(ctx, T.collect(findings))  # memory matches on tags found above

    if evidence and evidence.available:
        ev = evidence.for_protocol(prop.protocol_id)
        for f in findings:
            if not f.evidence and f.subject == prop.protocol_id:
                f.evidence = [{"kind": "document", **e} for e in ev[:3]]

    findings.sort(key=lambda f: (_SEV.get(f.severity, 9), f.rule, f.id))

    blocked = any(f.action == "block" for f in findings)
    caps = [f.cap_usd for f in findings if f.action == "cap" and f.cap_usd is not None]
    allowed = 0.0 if blocked else min([prop.amount_usd] + caps)
    if blocked:
        outcome = "BLOCK"
    elif allowed < prop.amount_usd:
        outcome = "ALLOW_WITH_CAP" if allowed > 0 else "BLOCK"
    elif any(f.action == "warn" for f in findings):
        outcome = "WARN"
    else:
        outcome = "ALLOW"

    gaps = []
    if not paths:
        gaps.append("no verified dependencies modelled")
    if facts.audits is None:
        gaps.append("audit data missing")
    if facts.age_days is None:
        gaps.append("listing age unknown")
    if evidence is not None and not evidence.available:
        gaps.append("evidence graph unavailable")

    return {
        "outcome": outcome, "proposal": prop.key(), "allowed_amount_usd": round(allowed, 2),
        "findings": [f.to_dict() for f in findings],
        "tags": T.collect(findings),
        "coverage": {"modelled": True, "dependency_paths": len(paths), "max_hops": hops,
                     "data_gaps": gaps, "capital_usd": capital, "tolerance_multiplier": mult},
        "rules_version": C.RULES_VERSION, "disclaimer": C.DISCLAIMER,
    }
