"""Deterministic rules. The LLM never decides a verdict; these functions do.

R1 shared-dependency concentration   R5 controller / admin-key risk
R2 young or unaudited protocol       R6 TVL collapse / reward-driven yield
R3 incident history (own + deps)     R7 learned memory rules + past mistakes
R4 stablecoin / peg dependency       R8 user preferences
R9 coverage (no verified deps)       S1 synthetic shock (what-if, in memory)

Each rule returns Findings that carry the graph path that justifies them.
Thresholds are illustrative policy (config.TH), not industry standards.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from . import config as C
from .graph_view import ProtocolFacts
from .models import Finding, PathRec, Proposal
from .propagation import best_paths, build_exposure, path_strength
from .util import days_between, pick, to_bool, to_float, to_int, usd

TH = C.TH


@dataclass
class Ctx:
    proposal: Proposal
    facts: ProtocolFacts
    amounts: dict[str, float]              # existing holdings (protocol -> usd), WITHOUT proposal
    capital: float
    mult: float                            # tolerance multiplier
    now: float
    paths: dict[str, PathRec]              # best eligible path per dependency of the proposal
    all_fwd: dict[str, list[PathRec]]      # eligible paths for proposal + holdings
    dep_incidents: dict[str, list[dict]]
    prefs: dict = field(default_factory=dict)
    memory_rules: list[dict] = field(default_factory=list)
    mistakes: list[dict] = field(default_factory=list)
    synthetic_shocks: list[dict] = field(default_factory=list)

    @property
    def key(self) -> str:
        return self.proposal.protocol_id

    @property
    def amount(self) -> float:
        return self.proposal.amount_usd

    def pct_cap(self, pct: float, scale: bool = True) -> float:
        return self.capital * pct * (self.mult if scale else 1.0) / 100.0


# ---- helpers -----------------------------------------------------------------
def _lbls(rec: PathRec) -> str:
    return " ".join(rec.other_labels).lower()


def is_controller(rec: PathRec) -> bool:
    return rec.rels[-1] == "GOVERNED_BY" or any(
        w in _lbls(rec) for w in ("controller", "multisig", "governance", "admin", "signer"))


def is_oracle(rec: PathRec) -> bool:
    return rec.rels[-1] == "USES_ORACLE" or "oracle" in _lbls(rec)


def is_stable(rec: PathRec) -> bool:
    return (pick(rec.other_props, C.PROPS["peg_mech"]) is not None
            or any(w in _lbls(rec) for w in ("stable", "asset", "token")))


def _evid(rec: PathRec) -> list[dict]:
    return rec.edge_evidence()


def _tags(*t: str) -> dict:
    return {"tags": list(t)}


# ---- R9 coverage -------------------------------------------------------------
def r9_coverage(c: Ctx) -> list[Finding]:
    if c.paths:
        return []
    return [Finding(
        "R9", "info",
        f"No verified dependencies are modelled for {c.facts.name}. This means unknown, not safe.",
        [c.key], c.key, "warn", details=_tags("no_verified_dependencies"))]


# ---- R1 concentration --------------------------------------------------------
def r1_concentration(c: Ctx) -> list[Finding]:
    out: list[Finding] = []
    amounts_after = dict(c.amounts)
    amounts_after[c.key] = amounts_after.get(c.key, 0.0) + c.amount
    capital = max(c.capital, sum(amounts_after.values()))
    before = {r["dependency"]: r for r in build_exposure(c.all_fwd, c.amounts, capital)}
    after = build_exposure(c.all_fwd, amounts_after, capital)
    limit_pct = TH["R1_SHARE_PCT"] * c.mult
    for row in after:
        if c.key not in row["protocols"] or row["share_pct"] <= limit_pct:
            continue
        existing = before.get(row["dependency"], {}).get("usd", 0.0)
        room = max(0.0, capital * limit_pct / 100.0 - existing)
        path = c.paths[row["dependency"]].nodes if row["dependency"] in c.paths else [c.key, row["dependency"]]
        rec = c.paths.get(row["dependency"])
        others = [p for p in row["protocols"] if p != c.key]
        out.append(Finding(
            "R1", "high",
            f"{row['share_pct']:.0f}% of capital would sit on {row['dependency']} "
            f"via {', '.join(row['protocols'])} (limit {limit_pct:.0f}%).",
            path, row["dependency"], "cap", min(room, c.amount),
            _evid(rec) if rec else [],
            details={**_tags("shared_dependency"), "share_pct": row["share_pct"],
                     "limit_pct": limit_pct, "also_exposed_via": others,
                     "paths": row["paths"]}))
    return out


# ---- R2 young / unaudited ----------------------------------------------------
def r2_young_unaudited(c: Ctx) -> list[Finding]:
    f, out = c.facts, []
    if f.audits == 0:
        out.append(Finding("R2", "medium",
                           f"{f.name} lists no audits (per DeFiLlama listing; absence is not proof of no audit).",
                           [c.key], c.key, "cap", c.pct_cap(TH["R2_CAP_PCT"]),
                           details=_tags("unaudited_listed")))
    elif f.audits is None:
        out.append(Finding("R2", "info", f"Audit data is missing for {f.name}.",
                           [c.key], c.key, "warn", details=_tags("audit_data_missing")))
    if f.age_days is not None and f.age_days < TH["R2_YOUNG_DAYS"]:
        out.append(Finding("R2", "medium",
                           f"{f.name} was listed only {f.age_days:.0f} days ago (< {TH['R2_YOUNG_DAYS']}).",
                           [c.key], c.key, "cap", c.pct_cap(TH["R2_CAP_PCT"]),
                           details=_tags("young_protocol")))
    return out


# ---- R3 incidents ------------------------------------------------------------
def _recent(inc: dict, now: float) -> bool:
    d = days_between(inc.get("ts"), now)
    return d is not None and 0 <= d <= TH["R3_RECENT_DAYS"]


def r3_incidents(c: Ctx) -> list[Finding]:
    out: list[Finding] = []
    own = c.facts.incidents
    if own:
        recent = [i for i in own if _recent(i, c.now)]
        major = [i for i in recent if (i.get("amount") or 0) >= TH["R3_MAJOR_LOSS_USD"]]
        worst = max(own, key=lambda i: i.get("amount") or 0)
        tags = ["incident_history"] + (["recent_incident"] if recent else [])
        out.append(Finding(
            "R3", "high" if major else "medium",
            f"{c.facts.name} has {len(own)} recorded incident(s); worst: "
            f"{worst.get('name') or 'unnamed'} ({usd(worst.get('amount') or 0)}).",
            [c.key], c.key, "cap" if recent else "warn",
            c.pct_cap(TH["R3_OWN_CAP_PCT"]) if recent else None,
            details={**_tags(*tags), "incidents": own[:5]}))
    for dep, incs in c.dep_incidents.items():
        rec = c.paths.get(dep)
        if rec is None or dep == c.key:
            continue
        recent = [i for i in incs if _recent(i, c.now)]
        if not recent:
            continue
        w = max(recent, key=lambda i: i.get("amount") or 0)
        out.append(Finding(
            "R3", "high",
            f"{c.facts.name} depends on {dep} ({' > '.join(rec.nodes)}), which had a recent incident: "
            f"{w.get('name') or 'unnamed'} ({usd(w.get('amount') or 0)}).",
            rec.nodes, dep, "cap", c.pct_cap(TH["R3_DEP_CAP_PCT"]), _evid(rec),
            details={**_tags("dependency_incident"), "incidents": recent[:3]}))
    return out


# ---- R4 peg ------------------------------------------------------------------
def r4_peg(c: Ctx) -> list[Finding]:
    out: list[Finding] = []
    for dep, rec in c.paths.items():
        if not is_stable(rec):
            continue
        p = rec.other_props
        mech = str(pick(p, C.PROPS["peg_mech"]) or "").lower()
        dev = to_float(pick(p, C.PROPS["peg_dev_pct"]))
        price, ptype = to_float(pick(p, C.PROPS["price"])), str(pick(p, C.PROPS["peg_type"]) or "")
        if dev is None and price is not None and ptype.lower() in ("peggedusd", "usd"):
            dev = abs(price - 1.0) * 100.0
        if dev is not None and abs(dev) > TH["R4_PEG_DEVIATION_PCT"]:
            out.append(Finding(
                "R4", "high", f"{dep} (a dependency of {c.facts.name}) trades {abs(dev):.2f}% off peg.",
                rec.nodes, dep, "block", 0.0, _evid(rec), details=_tags("depegged_stablecoin")))
        elif "algo" in mech:
            out.append(Finding(
                "R4", "medium", f"{c.facts.name} depends on {dep}, an algorithmic stablecoin.",
                rec.nodes, dep, "cap", c.pct_cap(TH["R2_CAP_PCT"]), _evid(rec),
                details=_tags("algorithmic_stablecoin")))
    return out


# ---- R5 controllers ----------------------------------------------------------
def r5_controller(c: Ctx) -> list[Finding]:
    out: list[Finding] = []
    for dep, rec in c.paths.items():
        if not is_controller(rec):
            continue
        p = rec.other_props
        ctype = str(pick(p, C.PROPS["ctrl_type"]) or "").lower()
        thr = to_int(pick(p, C.PROPS["ctrl_threshold"]))
        tl = to_float(pick(p, C.PROPS["ctrl_timelock"]))
        if ctype in ("eoa", "single_key", "owner") or (thr is not None and thr <= 1):
            out.append(Finding(
                "R5", "high", f"{c.facts.name} is controlled by a single key ({dep}).",
                rec.nodes, dep, "cap", c.pct_cap(TH["R5_EOA_CAP_PCT"]), _evid(rec),
                details=_tags("admin_eoa")))
        elif thr is not None and thr < TH["R5_MIN_SIGNERS"]:
            out.append(Finding(
                "R5", "medium", f"{dep} needs only {thr} signer(s) (< {TH['R5_MIN_SIGNERS']}).",
                rec.nodes, dep, "cap", c.pct_cap(TH["R5_WEAK_CAP_PCT"]), _evid(rec),
                details=_tags("weak_multisig")))
        if tl is not None and tl <= 0:
            out.append(Finding("R5", "low", f"{dep} has no timelock.", rec.nodes, dep, "warn",
                               evidence=_evid(rec), details=_tags("no_timelock")))
    oracles = [r for r in c.paths.values() if is_oracle(r) and r.hops == 1]
    if len(oracles) == 1:
        o = oracles[0]
        out.append(Finding("R5", "low", f"{c.facts.name} has a single modelled oracle ({o.other}).",
                           o.nodes, o.other, "warn", evidence=_evid(o), details=_tags("single_oracle")))
    return out


# ---- R6 market signals -------------------------------------------------------
def r6_market(c: Ctx) -> list[Finding]:
    f, out = c.facts, []
    if f.change_7d is not None and f.change_7d <= TH["R6_TVL_DROP_7D_PCT"]:
        out.append(Finding("R6", "medium", f"{f.name} TVL fell {abs(f.change_7d):.0f}% in 7 days.",
                           [c.key], c.key, "warn", details=_tags("tvl_drop")))
    outliers = [p for p in f.pools if p.get("outlier")]
    if outliers:
        out.append(Finding("R6", "low", f"{len(outliers)} pool(s) of {f.name} are flagged as APY outliers.",
                           [c.key], c.key, "warn", details=_tags("high_apy_outlier")))
    rewarded = [p for p in f.pools if p.get("apy") and p.get("apy_reward") is not None
                and 100.0 * p["apy_reward"] / p["apy"] >= TH["R6_REWARD_SHARE_PCT"]]
    if rewarded:
        out.append(Finding("R6", "low", f"Yield on {len(rewarded)} pool(s) of {f.name} is mostly token rewards.",
                           [c.key], c.key, "warn", details=_tags("reward_driven_yield")))
    return out


# ---- R7 memory ---------------------------------------------------------------
def r7_memory(c: Ctx, tags: list[str]) -> list[Finding]:
    out: list[Finding] = []
    for r in c.memory_rules:
        if r.get("tag") not in tags:
            continue
        act = r.get("action", "warn")
        cap = c.pct_cap(float(r["cap_pct"]), scale=False) if act == "cap" and r.get("cap_pct") is not None else None
        out.append(Finding(
            "R7", "high" if act == "block" else "medium",
            f"Your rule: {r.get('note') or r.get('tag')}", [c.key], c.key,
            act if act in ("block", "cap", "warn") else "warn", cap if act == "cap" else None,
            memory_ref={"kind": "rule", "id": r.get("id"), "tag": r.get("tag")}))
    for m in c.mistakes:
        if m.get("tag") in tags:
            out.append(Finding(
                "R7", "medium", f"You lost money on this pattern before: {m.get('summary') or m.get('tag')}",
                [c.key], c.key, "warn",
                memory_ref={"kind": "mistake", "id": m.get("id"), "tag": m.get("tag")}))
    return out


# ---- R8 preferences ----------------------------------------------------------
def r8_prefs(c: Ctx) -> list[Finding]:
    p, out = c.prefs or {}, []
    if (p.get("max_position_pct") is not None):
        lim = c.pct_cap(float(p["max_position_pct"]), scale=False)
        held = c.amounts.get(c.key, 0.0)
        if held + c.amount > lim:
            out.append(Finding("R8", "medium",
                               f"Your max position size is {p['max_position_pct']}% of capital.",
                               [c.key], c.key, "cap", max(0.0, lim - held)))
    cat = (c.facts.category or "").lower()
    if cat and cat in [str(x).lower() for x in p.get("avoid_categories", [])]:
        out.append(Finding("R8", "high", f"You asked to avoid the {c.facts.category} category.",
                           [c.key], c.key, "block", 0.0))
    bad = [x for x in c.facts.chains if x.lower() in [str(y).lower() for y in p.get("avoid_chains", [])]]
    if bad:
        out.append(Finding("R8", "high", f"You asked to avoid chain(s): {', '.join(bad)}.",
                           [c.key], c.key, "block", 0.0))
    return out


# ---- S1 synthetic shock ------------------------------------------------------
def s1_synthetic(c: Ctx) -> list[Finding]:
    out: list[Finding] = []
    for s in c.synthetic_shocks:
        node, sev = s.get("node"), max(0.0, min(1.0, to_float(s.get("severity")) or 1.0))
        if node == c.key:
            frac, path, rec = sev, [c.key], None
        elif node in c.paths:
            rec = c.paths[node]
            frac, path = sev * path_strength(rec), rec.nodes
        else:
            continue
        loss = c.amount * frac
        act = "cap" if frac >= 0.25 else "warn"
        out.append(Finding(
            "S1", "medium", f"What-if: {node} fails at severity {sev:.2f}; estimated loss on this "
            f"position about {usd(loss)} (estimate, not a prediction).", path, node, act,
            (c.capital * 0.05 / frac) if act == "cap" and frac > 0 else None,
            _evid(rec) if rec else [],
            details={"synthetic": True, "estimated_loss_usd": round(loss, 2), "impact_fraction": round(frac, 4)}))
    return out
