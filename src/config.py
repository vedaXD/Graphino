"""Single place to adapt the risk engine to your graph's actual schema and policy.

Everything that is an ASSUMPTION about your data lives here. Run
`python -m risk_engine.cli diagnose` first: it prints the labels, relationship
types and property keys that really exist, and how many dependency edges pass
the eligibility predicate. Then edit this file if names differ.

Thresholds are illustrative policy, not industry standards. Say so in the README.
"""
from __future__ import annotations

import os

# ---- connection -----------------------------------------------------------
RISK_GRAPH = os.getenv("RISK_GRAPH", "defi_risk")
EVIDENCE_GRAPH = os.getenv("EVIDENCE_GRAPH", "defi_evidence")
MEMORY_PREFIX = os.getenv("FALKORDB_GRAPH_MEMORY_PREFIX", "mem_")
FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
FALKORDB_USERNAME = os.getenv("FALKORDB_USERNAME") or None
FALKORDB_PASSWORD = os.getenv("FALKORDB_PASSWORD") or None
FALKORDB_LITE_PATH = os.getenv("FALKORDB_LITE_PATH") or None  # embedded DB, used by tests


def memory_graph_name(user_id: str) -> str:
    """Create a safe, deterministic per-user graph name."""
    safe_id = "".join(c for c in user_id.lower() if c.isalnum() or c in "_-")
    if not safe_id:
        raise ValueError("user_id must contain at least one alphanumeric character")
    return f"{MEMORY_PREFIX}{safe_id}"

# ---- which relationships may carry risk -----------------------------------
# Direction convention: (A)-[:DEPENDS_ON]->(B) means "A depends on B".
# A shock at B therefore propagates BACKWARDS along incoming edges.
DEPENDENCY_REL_TYPES = ("DEPENDS_ON", "USES_ORACLE", "GOVERNED_BY")

# Never carry risk, whatever their properties say. Listed only so `diagnose`
# can report them. (README: RELATED_TO is an association, not a dependency;
# ASSOCIATED_WITH_ASSET is a candidate association until promoted.)
NON_RISK_REL_TYPES = ("RELATED_TO", "ASSOCIATED_WITH_ASSET")

# Fail-closed eligibility: an edge carries risk only if it is explicitly
# risk_eligible AND explicitly verified AND not a test/synthetic edge.
# Edges missing these properties are EXCLUDED. `{r}` is the relationship alias.
#
# Your ingestion stores verification as `verification_status` (string), not a
# boolean `verified`, so either form is accepted. Run
#   MATCH ()-[e]->() RETURN type(e), e.verification_status, e.risk_eligible, e.kind, e.scope, count(*)
# in FalkorDB Browser and put the exact "verified" spellings you use below.
VERIFIED_STATUS_VALUES = ("verified", "source_verified", "curated_verified", "confirmed")
# Values of e.kind / e.scope / e.verification_status that mark test or unverified data.
TEST_MARKERS = ("test", "mock", "synthetic", "fixture", "demo")


def _in_list(values) -> str:
    return "[" + ", ".join("'" + v.replace("'", "") + "'" for v in values) + "]"


_DEFAULT_ELIGIBILITY = (
    "coalesce({r}.risk_eligible, false) = true "
    "AND (coalesce({r}.verified, false) = true "
    "OR toLower(coalesce({r}.verification_status, '')) IN " + _in_list(VERIFIED_STATUS_VALUES) + ") "
    "AND coalesce({r}.is_test, false) = false "
    "AND coalesce({r}.synthetic, false) = false "
    "AND NOT toLower(coalesce({r}.kind, '')) IN " + _in_list(TEST_MARKERS) + " "
    "AND NOT toLower(coalesce({r}.scope, '')) IN " + _in_list(TEST_MARKERS)
)
# Override with the RISK_ELIGIBILITY_PREDICATE env var if you need something else.
ELIGIBILITY_TEMPLATE = os.getenv("RISK_ELIGIBILITY_PREDICATE", _DEFAULT_ELIGIBILITY)

# How a node is identified across the graph (first non-null wins).
# Protocol has slug; Oracle/Asset/Controller/Chain/Incident/Pool use their own *_id.
NODE_KEY_PROPS = ("slug", "oracle_id", "asset_id", "controller_id", "chain_id",
                  "incident_id", "pool_id", "id", "name")

# ---- property-name candidates (first non-empty wins) ------------------------
PROPS = {
    "name": ("name",),
    "category": ("category",),
    "tvl": ("tvl_usd", "tvl"),
    "change_1d": ("change_1d",),
    "change_7d": ("change_7d", "tvl_change_7d"),
    "audits": ("audits", "audit_count"),  # DeFiLlama "audits" counts audits it LISTS
    "listed_at": ("listedAt", "listed_at"),
    "age_days": ("age_days", "listed_age_days"),
    "chains": ("chains",),
    # incidents
    "inc_name": ("name", "title"),
    "inc_date": ("date", "timestamp", "ts"),
    "inc_amount": ("amount_usd", "amount", "loss_usd"),
    "inc_class": ("classification", "type"),
    "inc_technique": ("technique",),
    "inc_bridge": ("bridge_hack", "bridgeHack", "is_bridge"),
    # pools
    "pool_symbol": ("symbol",),
    "pool_tvl": ("tvlUsd", "tvl_usd", "tvl"),
    "pool_apy": ("apy",),
    "pool_apy_base": ("apyBase", "apy_base"),
    "pool_apy_reward": ("apyReward", "apy_reward"),
    "pool_outlier": ("outlier",),
    "pool_il": ("il_risk", "ilRisk"),
    # stablecoin / asset
    "peg_mech": ("peg_mechanism", "raw_pegMechanism", "pegMechanism"),
    "peg_dev_pct": ("peg_deviation_pct",),
    "price": ("raw_price", "price"),
    "peg_type": ("peg_type", "pegType"),
    # controller
    "ctrl_type": ("controller_type", "type", "kind"),
    "ctrl_threshold": ("threshold",),
    "ctrl_timelock": ("timelock_hours", "timelock"),
}

# ---- policy thresholds (illustrative) ---------------------------------------
TH = {
    "MAX_HOPS": 3,                    # traversal depth (clamped to 1..4)
    "R1_SHARE_PCT": 40.0,             # one shared dependency above this % of capital
    "R2_YOUNG_DAYS": 90,              # "listed age" below this is young
    "R2_CAP_PCT": 5.0,
    "R3_RECENT_DAYS": 730,
    "R3_MAJOR_LOSS_USD": 10_000_000,
    "R3_OWN_CAP_PCT": 10.0,
    "R3_DEP_CAP_PCT": 5.0,
    "R4_PEG_DEVIATION_PCT": 1.0,
    "R5_EOA_CAP_PCT": 5.0,
    "R5_MIN_SIGNERS": 3,
    "R5_WEAK_CAP_PCT": 10.0,
    "R6_TVL_DROP_7D_PCT": -30.0,
    "R6_REWARD_SHARE_PCT": 70.0,
}

# A user's risk_tolerance scales percentage caps (not blocks).
TOLERANCE_MULT = {"conservative": 0.5, "moderate": 1.0, "aggressive": 1.5}

# Default edge strength when an edge has no `strength` property.
# Strength is a MODELLING JUDGMENT (how much of the dependent's value rests on
# the dependency). Impact numbers are estimates, never precise losses.
DEFAULT_STRENGTH = {"USES_ORACLE": 0.5, "GOVERNED_BY": 0.25, "DEPENDS_ON": 0.5}

# Controlled tag vocabulary (join key between the risk graph and user memory).
TAG_VOCABULARY = (
    "unaudited_listed", "audit_data_missing", "young_protocol", "tvl_drop",
    "incident_history", "recent_incident", "dependency_incident",
    "no_verified_dependencies", "single_oracle", "admin_eoa", "weak_multisig",
    "no_timelock", "algorithmic_stablecoin", "depegged_stablecoin",
    "high_apy_outlier", "reward_driven_yield", "shared_dependency",
)

# Evidence graph: properties that may link an Evidence node to a protocol.
EVIDENCE_LABEL = "Evidence"
EVIDENCE_LINK_PROPS = ("protocol_slug", "protocol_id", "slug", "protocol", "protocols", "entity_id")

RULES_VERSION = "2026-10-17.1"
DISCLAIMER = (
    "Verdicts reflect only modelled, verified data in the graph. ALLOW means no rule "
    "fired on that data; it does not mean a protocol is safe. Not financial advice. "
    "Paper trading only."
)