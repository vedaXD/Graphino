
from falkordb import FalkorDB
from dotenv import load_dotenv
import os
import time

load_dotenv()

HOST = os.getenv("FALKORDB_HOST", "localhost")
PORT = int(os.getenv("FALKORDB_PORT", "6379"))
USERNAME = os.getenv("FALKORDB_USERNAME") or None
PASSWORD = os.getenv("FALKORDB_PASSWORD") or None

RISK_GRAPH = os.getenv("FALKORDB_GRAPH_RISK", "defi_risk")
EVIDENCE_GRAPH = os.getenv(
    "FALKORDB_GRAPH_EVIDENCE", "defi_evidence"
)


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


def upsert_controller(graph, controller_id, name, kind, source_url):
    graph.query(
        """
        MERGE (c:Controller {controller_id: $controller_id})
        SET c.name = $name,
            c.controller_type = $kind,
            c.source_url = $source_url,
            c.updated_at = $updated_at
        """,
        {
            "controller_id": controller_id,
            "name": name,
            "kind": kind,
            "source_url": source_url,
            "updated_at": int(time.time()),
        },
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
    # Only connect to protocols already ingested.
    # The target node must also already exist.
    query = f"""
    MATCH (p:Protocol {{slug: $slug}})
    MATCH (t:{target_label} {{{target_key}: $target_id}})
    MERGE (p)-[r:{relationship}]->(t)
    SET r += $properties
    RETURN p.name, type(r), t.name
    """

    result = graph.query(
        query,
        {
            "slug": protocol_slug,
            "target_id": target_id,
            "properties": properties,
        },
    )

    if result.result_set:
        print("  Added/updated:", result.result_set[0])
    else:
        print(
            f"  SKIPPED: protocol '{protocol_slug}' or target "
            f"'{target_id}' not found"
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
        "https://www.aave.com/docs/ecosystem/oracle",
    )

    upsert_oracle(
        risk,
        "lido-accounting-oracle",
        "Lido AccountingOracle",
        "protocol_accounting_oracle",
        "https://docs.lido.fi/contracts/accounting-oracle/",
    )

    print("\n=== Creating governance node ===")

    upsert_controller(
        risk,
        "aave-governance",
        "Aave Governance",
        "governance",
        "https://www.aave.com/docs/ecosystem/oracle",
    )

    print("\n=== Adding sourced relationships ===")

    # Aave's documentation describes Chainlink price feeds in production
    # markets, but the actual oracle varies by market/reserve.
    # This is a broad dependency candidate, not proof every reserve
    # uses Chainlink.
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
            "source_url": (
                "https://www.aave.com/docs/ecosystem/oracle"
            ),
            "verification_status": "documented_general_dependency",
            "risk_eligible": False,
        },
    )

    add_relationship(
        risk,
        "aave-v3",
        "Oracle",
        "oracle_id",
        "chainlink-price-feeds",
        "USES_ORACLE",
        {
            "source_url": (
                "https://www.aave.com/docs/ecosystem/oracle"
            ),
            "scope": "market_specific",
            "verification_status": "documented_general_dependency",
        },
    )

    # Lido documents its AccountingOracle. This is an internal
    # protocol accounting dependency, not a claim that Lido uses Chainlink.
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
            "source_url": (
                "https://docs.lido.fi/contracts/accounting-oracle/"
            ),
            "verification_status": "documented",
        },
    )

    # Governance is documented as selecting the oracle for Aave reserves.
    add_relationship(
        risk,
        "aave-v3",
        "Controller",
        "controller_id",
        "aave-governance",
        "GOVERNED_BY",
        {
            "kind": "oracle_configuration_governance",
            "source_url": (
                "https://www.aave.com/docs/ecosystem/oracle"
            ),
            "verification_status": "documented",
        },
    )

    print("\n=== Adding evidence records ===")

    add_evidence(
        evidence,
        "aave-oracle-docs",
        "Aave Oracle Documentation",
        "aave-v3",
        "oracle_dependency",
        "https://www.aave.com/docs/ecosystem/oracle",
        (
            "Aave documents Chainlink Price Feeds and CAPO among "
            "production oracle types. Oracle selection is market/reserve-specific."
        ),
    )

    add_evidence(
        evidence,
        "lido-accounting-oracle-docs",
        "Lido AccountingOracle Documentation",
        "lido",
        "accounting_oracle",
        "https://docs.lido.fi/contracts/accounting-oracle/",
        (
            "Lido's AccountingOracle collects oracle reports, and the "
            "Accounting contract applies protocol state updates."
        ),
    )

    print("\nDone.")
    print("Inspect the risk graph and evidence graph to verify the records.")


if __name__ == "__main__":
    main()