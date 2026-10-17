"""Schema and policy configuration for Bulwark's deterministic risk engine.

Property names are aligned with the current DeFiLlama ingestion graph.
Thresholds are illustrative policy, not industry standards.
"""
from __future__ import annotations

import os

# ---- connection -----------------------------------------------------------
RISK_GRAPH = os.getenv("RISK_GRAPH", "defi_risk")
EVIDENCE_GRAPH = os.getenv("EVIDENCE_GRAPH", "defi_evidence")
FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
FALKORDB_USERNAME = os.getenv("FALKORDB_USERNAME") or None
FALKORDB_PASSWORD = os.getenv("FALKORDB_PASSWORD") or None
FALKORDB_LITE_PATH = os.getenv("FALKORDB_LITE_PATH") or None

# (A)-[:DEPENDS_ON]->(B) means A depends on B; shocks propagate backwards.
DEPENDENCY_REL_TYPES = ("DEPENDS_ON", "USES_ORACLE", "GOVERNED_BY")
NON_RISK_REL_TYPES = ("RELATED_TO", "ASSOCIATED_WITH_ASSET")

# Fail closed. A relationship must have risk_eligible=true AND explicit
# verification (either verified=true or a recognized verification_status).
# Missing properties do not imply eligibility. Test/synthetic edges are excluded.
ELIGIBILITY_TEMPLATE = os.getenv(
    "RISK_ELIGIBILITY_PREDICATE",
    "coalesce({r}.risk_eligible, false) = true "
    "AND (coalesce({r}.verified, false) = true "
    "OR toLower(coalesce({r}.verification_status, '')) "
    "IN ['verified', 'confirmed', 'source_verified']) "
    "AND coalesce({r}.is_test, false) = false "
    "AND coalesce({r}.synthetic, false) = false",
)

# Include the IDs actually used by the ingester and curated seed script.
NODE_KEY_PROPS = (
    "slug", "protocol_id", "oracle_id", "controller_id", "asset_id",
    "pool_id", "incident_id", "chain_id", "id", "name",
)

# ---- property-name candidates (first non-empty wins) ----------------------
PROPS = {
    "name": ("name",),
    "category": ("category",),
    "tvl": ("tvl_usd", "tvl"),
    "change_1d": ("change_1d",),
    # Current diagnostics do not show change_7d on Protocol nodes. Keep the
    # candidates for future data, but absent values remain unknown.
    "change_7d": ("change_7d", "tvl_change_7d"),
    "audits": ("audits", "audit_count"),
    "listed_at": ("listed_at", "listedAt"),
    "age_days": ("age_days", "listed_age_days"),
    "chains": ("chains",),

    # Incidents
    "inc_name": ("name", "title"),
    "inc_date": ("date", "timestamp", "ts"),
    "inc_amount": ("amount_usd", "amount", "loss_usd"),
    "inc_class": ("classification", "type"),
    "inc_technique": ("technique",),
    "inc_bridge": ("bridge_hack", "bridgeHack", "is_bridge"),

    # Pools
    "pool_symbol": ("symbol",),
    "pool_tvl": ("tvl_usd", "tvlUsd", "tvl"),
    "pool_apy": ("apy",),
    "pool_apy_base": ("apy_base", "apyBase"),
    "pool_apy_reward": ("apy_reward", "apyReward"),
    "pool_outlier": ("outlier",),
    "pool_il": ("il_risk", "ilRisk"),

    # Stablecoin / asset. Current Asset nodes use raw_price and raw_pegMechanism.
    "peg_mech": ("peg_mechanism", "raw_pegMechanism", "peg_type", "pegMechanism"),
    "peg_dev_pct": ("peg_deviation_pct",),
    "price": ("raw_price", "price"),
    "peg_type": ("peg_type", "pegType"),

    # Controller
    "ctrl_type": ("controller_type", "type", "kind"),
    "ctrl_threshold": ("threshold", "signer_threshold", "required_signers"),
    "ctrl_timelock": ("timelock_hours", "timelock"),
}

# ---- policy thresholds (illustrative) -------------------------------------
TH = {
    "MAX_HOPS": 3,
    "R1_SHARE_PCT": 40.0,
    "R2_YOUNG_DAYS": 90,
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

TOLERANCE_MULT = {"conservative": 0.5, "moderate": 1.0, "aggressive": 1.5}
DEFAULT_STRENGTH = {"USES_ORACLE": 0.5, "GOVERNED_BY": 0.25, "DEPENDS_ON": 0.5}

TAG_VOCABULARY = (
    "unaudited_listed", "audit_data_missing", "young_protocol", "tvl_drop",
    "incident_history", "recent_incident", "dependency_incident",
    "no_verified_dependencies", "single_oracle", "admin_eoa", "weak_multisig",
    "no_timelock", "algorithmic_stablecoin", "depegged_stablecoin",
    "high_apy_outlier", "reward_driven_yield", "shared_dependency",
)

EVIDENCE_LABEL = "Evidence"
EVIDENCE_LINK_PROPS = (
    "protocol_slug", "protocol_id", "slug", "protocol", "protocols", "entity_id",
)
RULES_VERSION = "2026-10-18.1"
DISCLAIMER = (
    "Verdicts reflect only modelled, verified data in the graph. ALLOW means no rule "
    "fired on that data; it does not mean a protocol is safe. Not financial advice. "
    "Paper trading only."
)