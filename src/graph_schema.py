"""
Bulwark graph schema registry.

FalkorDB is schema-flexible: labels and relationship types are introduced by
CREATE/MERGE queries. This file documents the intended model and declares
indexes for fields commonly used in lookups.
"""

# Graph name -> node labels and key fields.
GRAPH_SCHEMA = {
    "defi_risk": {
        "Protocol": ["protocol_id", "slug", "name", "category", "tvl_usd", "listed_at"],
        "Chain": ["chain_id", "name", "chain_id_numeric"],
        "Asset": ["asset_id", "symbol", "name", "asset_type", "peg"],
        "Pool": ["pool_id", "project", "chain", "symbol", "tvl_usd"],
        "Oracle": ["oracle_id", "name", "kind"],
        "Bridge": ["bridge_id", "name"],
        "Controller": ["controller_id", "name", "controller_type"],
        "Auditor": ["auditor_id", "name"],
        "Incident": ["incident_id", "name", "date", "classification", "amount_usd"],
        "Tag": ["name"],
    },
    "defi_evidence": {
        "Evidence": ["evidence_id", "title", "source_url", "published_at", "retrieved_at", "finding_type"],
        "Finding": ["finding_id", "title", "severity"],
    },
    "mem_<user_id>": {
        "User": ["user_id"],
        "Preference": ["key", "value", "strength", "updated_at"],
        "Episode": ["episode_id", "ts", "kind", "summary", "outcome"],
        "Mistake": ["mistake_id", "summary", "created_at"],
        "Rule": ["rule_id", "text", "action", "status", "confidence"],
        "ProtocolRef": ["protocol_id", "slug"],
        "Position": ["position_id", "protocol_id", "status", "size_pct"],
        "Session": ["session_id", "started_at", "summary"],
        "Turn": ["turn_id", "role", "created_at"],
        "Task": ["task_id", "kind", "status", "created_at"],
    },
}

# FalkorDB uses schema-flexible labels; these indexes make common MATCH lookups faster.
# If a server/client version rejects an index statement, init_graphs.py logs it and continues.
INDEX_STATEMENTS = {
    "defi_risk": [
        "CREATE INDEX FOR (n:Protocol) ON (n.protocol_id)",
        "CREATE INDEX FOR (n:Protocol) ON (n.slug)",
        "CREATE INDEX FOR (n:Protocol) ON (n.name)",
        "CREATE INDEX FOR (n:Chain) ON (n.chain_id)",
        "CREATE INDEX FOR (n:Asset) ON (n.asset_id)",
        "CREATE INDEX FOR (n:Asset) ON (n.symbol)",
        "CREATE INDEX FOR (n:Pool) ON (n.pool_id)",
        "CREATE INDEX FOR (n:Oracle) ON (n.oracle_id)",
        "CREATE INDEX FOR (n:Bridge) ON (n.bridge_id)",
        "CREATE INDEX FOR (n:Controller) ON (n.controller_id)",
        "CREATE INDEX FOR (n:Auditor) ON (n.auditor_id)",
        "CREATE INDEX FOR (n:Incident) ON (n.incident_id)",
        "CREATE INDEX FOR (n:Tag) ON (n.name)",
    ],
    "defi_evidence": [
        "CREATE INDEX FOR (n:Evidence) ON (n.evidence_id)",
        "CREATE INDEX FOR (n:Evidence) ON (n.source_url)",
        "CREATE INDEX FOR (n:Finding) ON (n.finding_id)",
    ],
    # Each memory graph receives the same indexes.
    "memory": [
        "CREATE INDEX FOR (n:User) ON (n.user_id)",
        "CREATE INDEX FOR (n:Preference) ON (n.key)",
        "CREATE INDEX FOR (n:Episode) ON (n.episode_id)",
        "CREATE INDEX FOR (n:Mistake) ON (n.mistake_id)",
        "CREATE INDEX FOR (n:Rule) ON (n.rule_id)",
        "CREATE INDEX FOR (n:ProtocolRef) ON (n.protocol_id)",
        "CREATE INDEX FOR (n:Position) ON (n.position_id)",
        "CREATE INDEX FOR (n:Session) ON (n.session_id)",
        "CREATE INDEX FOR (n:Turn) ON (n.turn_id)",
        "CREATE INDEX FOR (n:Task) ON (n.task_id)",
    ],
}

# Relationship types are created by MERGE/CREATE, not pre-declared in FalkorDB.
RELATIONSHIPS = {
    "defi_risk": [
        "DEPENDS_ON", "DEPLOYED_ON", "USES_ASSET", "ISSUES_ASSET",
        "HAS_POOL", "HAS_TAG", "AFFECTED_BY", "AUDITED_BY",
        "CONTROLLED_BY", "USES_ORACLE", "ROUTES_THROUGH",
        "FORKED_FROM", "RELATED_TO",
    ],
    "defi_evidence": ["ABOUT_PROTOCOL", "DOCUMENTS_INCIDENT", "SUPPORTS_FINDING"],
    "memory": [
        "HAS_PREFERENCE", "INVOLVED", "HAD_TAG", "FROM_EPISODE",
        "CAUSED_BY_TAG", "DERIVED_FROM", "REFERENCES_PROTOCOL",
        "HAS_POSITION", "HAS_SESSION", "HAS_TURN", "ASSIGNED_TO",
        "HANDOFF_TO", "BLOCKED_BY",
    ],
}
