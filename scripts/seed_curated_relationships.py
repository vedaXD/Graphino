"""Curated, source-backed relationship and evidence seeding for Bulwark.

Sets up verified dependencies for multi-hop risk analysis and documents evidence provenance.
Maintains fail-closed semantics: edges are only risk_eligible when backed by official documentation.
"""
from __future__ import annotations

import os
import time
from dotenv import load_dotenv
from falkordb import FalkorDB

load_dotenv()

HOST = os.getenv("FALKORDB_HOST", "localhost")
PORT = int(os.getenv("FALKORDB_PORT", "6379"))
USERNAME = os.getenv("FALKORDB_USERNAME") or None
PASSWORD = os.getenv("FALKORDB_PASSWORD") or None

RISK_GRAPH = os.getenv("FALKORDB_GRAPH_RISK", "defi_risk")
EVIDENCE_GRAPH = os.getenv("FALKORDB_GRAPH_EVIDENCE", "defi_evidence")


def connect():
    kwargs = {"host": HOST, "port": PORT}
    if USERNAME:
        kwargs["username"] = USERNAME
    if PASSWORD:
        kwargs["password"] = PASSWORD
    return FalkorDB(**kwargs)


def upsert_oracle(graph, oracle_id, name, kind, source_url):
    graph.query(
        """
        MERGE (o:Oracle {oracle_id: $oracle_id})
        SET o.name = $name,
            o.kind = $kind,
            o.source_url = $source_url,
            o.updated_at = $updated_at
        """,
        {
            "oracle_id": oracle_id,
            "name": name,
            "kind": kind,
            "source_url": source_url,
            "updated_at": int(time.time()),
        },
    )


def upsert_controller(graph, controller_id, name, kind, source_url, threshold=None, timelock_hours=None):
    graph.query(
        """
        MERGE (c:Controller {controller_id: $controller_id})
        SET c.name = $name,
            c.controller_type = $kind,
            c.threshold = $threshold,
            c.timelock_hours = $timelock_hours,
            c.source_url = $source_url,
            c.updated_at = $updated_at
        """,
        {
            "controller_id": controller_id,
            "name": name,
            "kind": kind,
            "threshold": threshold,
            "timelock_hours": timelock_hours,
            "source_url": source_url,
            "updated_at": int(time.time()),
        },
    )


def add_entity_relationship(
    graph,
    source_label,
    source_key,
    source_id,
    target_label,
    target_key,
    target_id,
    relationship,
    properties,
):
    query = f"""
    MATCH (s:{source_label} {{{source_key}: $source_id}})
    MATCH (t:{target_label} {{{target_key}: $target_id}})
    MERGE (s)-[r:{relationship}]->(t)
    SET r += $properties
    RETURN coalesce(s.name, s.slug, s.oracle_id), type(r), coalesce(t.name, t.slug, t.controller_id, t.oracle_id)
    """
    result = graph.query(
        query,
        {
            "source_id": source_id,
            "target_id": target_id,
            "properties": properties,
        },
    )
    if result.result_set:
        print("  Added/updated:", result.result_set[0])
    else:
        print(
            f"  SKIPPED: source '{source_id}' ({source_label}) or target "
            f"'{target_id}' ({target_label}) not found"
        )


def add_relationship(
    graph,
    protocol_slug,
    target_label,
    target_key,
    target_id,
    relationship,
    properties,
):
    add_entity_relationship(
        graph,
        "Protocol",
        "slug",
        protocol_slug,
        target_label,
        target_key,
        target_id,
        relationship,
        properties,
    )


def add_evidence(
    graph,
    evidence_id,
    title,
    protocol_id,
    finding_type,
    source_url,
    summary,
):
    graph.query(
        """
        MERGE (e:Evidence {evidence_id: $evidence_id})
        SET e.title = $title,
            e.protocol_id = $protocol_id,
            e.finding_type = $finding_type,
            e.source_url = $source_url,
            e.summary = $summary,
            e.retrieved_at = $retrieved_at,
            e.provenance = 'official_documentation'
        """,
        {
            "evidence_id": evidence_id,
            "title": title,
            "protocol_id": protocol_id,
            "finding_type": finding_type,
            "source_url": source_url,
            "summary": summary,
            "retrieved_at": int(time.time()),
        },
    )
    print("  Evidence upserted:", evidence_id)


def main():
    db = connect()
    risk = db.select_graph(RISK_GRAPH)
    evidence = db.select_graph(EVIDENCE_GRAPH)

    print("\n=== Creating oracle nodes ===")

    upsert_oracle(
        risk,
        "chainlink-price-feeds",
        "Chainlink Price Feeds",
        "external_price_oracle",
        "https://docs.aave.com/developers/core-contracts/aaveoracle",
    )

    upsert_oracle(
        risk,
        "lido-accounting-oracle",
        "Lido AccountingOracle",
        "protocol_accounting_oracle",
        "https://docs.lido.fi/contracts/accounting-oracle/",
    )

    print("\n=== Creating controller / governance nodes ===")

    upsert_controller(
        risk,
        "aave-governance",
        "Aave Governance",
        "governance",
        "https://docs.aave.com/governance/",
        threshold=3,
        timelock_hours=24,
    )

    # Chainlink Decentralized Oracle Network / Node Operator quorum
    upsert_controller(
        risk,
        "chainlink-node-operators",
        "Chainlink Node Operator Network",
        "multisig",
        "https://docs.chain.link/architecture-overview/architecture-decentralized-model",
        threshold=21,
        timelock_hours=0,
    )

    print("\n=== Adding verified multi-hop dependency relationships ===")

    # 1. Aave V3 -> Chainlink Price Feeds (USES_ORACLE: Verified, Hop 1)
    # Source: Aave V3 developer docs confirm AaveOracle relies on Chainlink price aggregators for reserves
    add_relationship(
        risk,
        "aave-v3",
        "Oracle",
        "oracle_id",
        "chainlink-price-feeds",
        "USES_ORACLE",
        {
            "kind": "price_oracle",
            "strength": 0.8,
            "confidence": 1.0,
            "scope": "core_market_reserves",
            "source_url": "https://docs.aave.com/developers/core-contracts/aaveoracle",
            "verification_status": "source_verified",
            "verified": True,
            "risk_eligible": True,
            "is_test": False,
            "synthetic": False,
        },
    )

    # 2. SparkLend -> Chainlink Price Feeds (USES_ORACLE: Verified, Hop 1 - Shared Dependency)
    # Source: SparkLend developer docs confirm Chainlink is the primary price oracle for collateral/borrow valuation
    add_relationship(
        risk,
        "sparklend",
        "Oracle",
        "oracle_id",
        "chainlink-price-feeds",
        "USES_ORACLE",
        {
            "kind": "price_oracle",
            "strength": 0.8,
            "confidence": 1.0,
            "scope": "sparklend_market_reserves",
            "source_url": "https://docs.spark.fi/developers/oracles",
            "verification_status": "source_verified",
            "verified": True,
            "risk_eligible": True,
            "is_test": False,
            "synthetic": False,
        },
    )

    # 3. Chainlink Price Feeds -> Chainlink Node Operators (DEPENDS_ON: Verified, Hop 2 Upstream Infrastructure)
    # Source: Chainlink architecture documentation detailing decentralized data aggregation by independent node operators
    add_entity_relationship(
        risk,
        "Oracle",
        "oracle_id",
        "chainlink-price-feeds",
        "Controller",
        "controller_id",
        "chainlink-node-operators",
        "DEPENDS_ON",
        {
            "kind": "node_operator_consensus",
            "strength": 0.9,
            "confidence": 1.0,
            "scope": "decentralized_oracle_network",
            "source_url": "https://docs.chain.link/architecture-overview/architecture-decentralized-model",
            "verification_status": "source_verified",
            "verified": True,
            "risk_eligible": True,
            "is_test": False,
            "synthetic": False,
        },
    )

    # 4. Aave V3 -> Aave Governance (GOVERNED_BY: Verified, Hop 1)
    # Source: Aave Governance documentation
    add_relationship(
        risk,
        "aave-v3",
        "Controller",
        "controller_id",
        "aave-governance",
        "GOVERNED_BY",
        {
            "kind": "protocol_governance",
            "strength": 0.5,
            "confidence": 1.0,
            "scope": "pool_admin_and_oracle_selection",
            "source_url": "https://docs.aave.com/governance/",
            "verification_status": "source_verified",
            "verified": True,
            "risk_eligible": True,
            "is_test": False,
            "synthetic": False,
        },
    )

    print("\n=== Adding unverified / candidate relationships (ineligible for risk propagation) ===")

    # Lido documents its AccountingOracle. This is an internal protocol accounting dependency,
    # not an external price oracle that triggers collateral liquidations. Left ineligible.
    add_relationship(
        risk,
        "lido",
        "Oracle",
        "oracle_id",
        "lido-accounting-oracle",
        "USES_ORACLE",
        {
            "kind": "accounting_oracle",
            "strength": 1.0,
            "confidence": 1.0,
            "source_url": "https://docs.lido.fi/contracts/accounting-oracle/",
            "verification_status": "documented_internal_oracle",
            "verified": False,
            "risk_eligible": False,
            "is_test": False,
            "synthetic": False,
        },
    )

    # Broad candidate dependency: un-scoped general DEPENDS_ON relationship left ineligible
    add_relationship(
        risk,
        "aave-v3",
        "Oracle",
        "oracle_id",
        "chainlink-price-feeds",
        "DEPENDS_ON",
        {
            "kind": "price_oracle",
            "strength": 0.7,
            "confidence": 0.8,
            "scope": "market_specific",
            "source_url": "https://www.aave.com/docs/ecosystem/oracle",
            "verification_status": "documented_general_dependency",
            "verified": False,
            "risk_eligible": False,
            "is_test": False,
            "synthetic": False,
        },
    )

    print("\n=== Adding evidence records to defi_evidence ===")

    add_evidence(
        evidence,
        "aave-v3-chainlink-oracle",
        "Aave V3 Price Oracle Documentation",
        "aave-v3",
        "oracle_dependency",
        "https://docs.aave.com/developers/core-contracts/aaveoracle",
        "Aave V3 uses AaveOracle as the primary price provider, fetching reserve asset valuations from Chainlink Aggregator feeds.",
    )

    add_evidence(
        evidence,
        "sparklend-chainlink-oracle",
        "SparkLend Oracle Documentation",
        "sparklend",
        "oracle_dependency",
        "https://docs.spark.fi/developers/oracles",
        "SparkLend uses Chainlink price feeds as the primary oracle for collateral and borrow valuation.",
    )

    add_evidence(
        evidence,
        "chainlink-don-architecture",
        "Chainlink Decentralized Oracle Network Architecture",
        "chainlink-price-feeds",
        "oracle_infrastructure_dependency",
        "https://docs.chain.link/architecture-overview/architecture-decentralized-model",
        "Chainlink price feeds depend on decentralized oracle networks consisting of independent node operators aggregating multi-source off-chain data.",
    )

    add_evidence(
        evidence,
        "aave-governance-docs",
        "Aave Governance V3 Documentation",
        "aave-v3",
        "governance_dependency",
        "https://docs.aave.com/governance/",
        "Aave Governance executes protocol upgrades, market parameter modifications, and oracle feed configurations via Timelock controllers.",
    )

    add_evidence(
        evidence,
        "lido-accounting-oracle-docs",
        "Lido AccountingOracle Documentation",
        "lido",
        "accounting_oracle",
        "https://docs.lido.fi/contracts/accounting-oracle/",
        "Lido's AccountingOracle collects oracle reports, and the Accounting contract applies protocol state updates.",
    )

    print("\nDone seeding curated relationships and evidence.")


if __name__ == "__main__":
    main()