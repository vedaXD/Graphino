"""Tests validating curated, source-backed dependencies and fail-closed edge eligibility."""
import pytest
from risk_engine import RiskGraph
from risk_engine.propagation import simulate_shock, portfolio_exposure
from scripts.seed_curated_relationships import main as run_seed_script


def test_seed_idempotent_no_duplicates(db):
    """Requirement 7: Running the seed script twice does not create duplicate nodes or edges."""
    run_seed_script()
    run_seed_script()

    g = db.select_graph("defi_risk")
    # Verify exact counts of curated entities
    r_oracle = g.query("MATCH (o:Oracle {oracle_id: 'chainlink-price-feeds'}) RETURN count(o)").result_set[0][0]
    assert r_oracle == 1

    r_controller = g.query("MATCH (c:Controller {controller_id: 'chainlink-node-operators'}) RETURN count(c)").result_set[0][0]
    assert r_controller == 1

    r_edge = g.query(
        "MATCH (:Protocol {slug: 'aave-v3'})-[r:USES_ORACLE]->(:Oracle {oracle_id: 'chainlink-price-feeds'}) "
        "RETURN count(r)"
    ).result_set[0][0]
    assert r_edge == 1


def test_source_verified_dependency_is_eligible(db):
    """Requirement 1: A source-verified dependency is eligible."""
    rg = RiskGraph(db, graph_name="defi_risk")
    diag = rg.diagnostics()
    assert diag["eligible_dependency_edges"] >= 4
    assert diag["dependency_edge_types"]["USES_ORACLE"]["eligible"] >= 2
    assert diag["dependency_edge_types"]["DEPENDS_ON"]["eligible"] >= 1
    assert diag["dependency_edge_types"]["GOVERNED_BY"]["eligible"] >= 1


def test_unverified_relationship_is_excluded(db):
    """Requirement 2: An unverified relationship is excluded from propagation."""
    rg = RiskGraph(db, graph_name="defi_risk")
    # Lido -> lido-accounting-oracle has verified=false, risk_eligible=false
    # A shock on lido-accounting-oracle must not affect Lido
    shock = simulate_shock(rg, "lido-accounting-oracle", severity=1.0)
    affected_nodes = {a["node"] for a in shock["affected"]}
    assert "lido" not in affected_nodes


def test_test_relationship_is_excluded(db):
    """Requirement 3: A test relationship (is_test=true) is excluded."""
    rg = RiskGraph(db, graph_name="defi_risk")
    # Test relationship from test_graph.py: (:Protocol {slug: 'compound'})-[:DEPENDS_ON {is_test: true}]->(:Oracle {oracle_id: 'chainlink'})
    shock = simulate_shock(rg, "chainlink", severity=1.0)
    affected_nodes = {a["node"] for a in shock["affected"]}
    assert "compound" not in affected_nodes
    assert "aave" not in affected_nodes


def test_related_to_does_not_carry_risk(db):
    """Requirement 4: A RELATED_TO association does not carry risk."""
    rg = RiskGraph(db, graph_name="defi_risk")
    diag = rg.diagnostics()
    assert diag["dependency_edge_types"]["RELATED_TO"]["eligible"] == 0
    assert not diag["dependency_edge_types"]["RELATED_TO"]["carries_risk"]


def test_synthetic_shock_propagates_multihop_along_eligible_edges_with_provenance(db):
    """Requirements 5 & 6: Synthetic shock propagates only along eligible edges and returns path + provenance."""
    rg = RiskGraph(db, graph_name="defi_risk")
    shock = simulate_shock(rg, "chainlink-node-operators", severity=0.8, max_hops=3)

    assert shock["outcome"] == "ok"
    by_node = {a["node"]: a for a in shock["affected"]}

    # Hop 1: Oracle
    assert "chainlink-price-feeds" in by_node
    oracle_res = by_node["chainlink-price-feeds"]
    assert oracle_res["hops"] == 1
    assert oracle_res["path"] == ["chainlink-price-feeds", "chainlink-node-operators"]
    assert oracle_res["evidence"][0]["source_url"] == "https://docs.chain.link/architecture-overview/architecture-decentralized-model"

    # Hop 2: Protocols (Aave V3 and SparkLend)
    assert "aave-v3" in by_node
    assert "sparklend" in by_node

    aave_res = by_node["aave-v3"]
    assert aave_res["hops"] == 2
    assert aave_res["path"] == ["aave-v3", "chainlink-price-feeds", "chainlink-node-operators"]
    assert aave_res["rels"] == ["USES_ORACLE", "DEPENDS_ON"]
    # Verified evidence URLs must be present
    urls = [e["source_url"] for e in aave_res["evidence"]]
    assert "https://docs.aave.com/developers/core-contracts/aaveoracle" in urls
    assert "https://docs.chain.link/architecture-overview/architecture-decentralized-model" in urls

    spark_res = by_node["sparklend"]
    assert spark_res["hops"] == 2
    assert spark_res["path"] == ["sparklend", "chainlink-price-feeds", "chainlink-node-operators"]
    spark_urls = [e["source_url"] for e in spark_res["evidence"]]
    assert "https://docs.spark.fi/developers/oracles" in spark_urls


def test_portfolio_exposure_identifies_shared_multihop_dependencies(db):
    """Validates multi-hop shared dependency exposure calculation."""
    rg = RiskGraph(db, graph_name="defi_risk")
    exposure = portfolio_exposure(
        rg,
        [{"protocol_id": "aave-v3", "amount_usd": 1000}, {"protocol_id": "sparklend", "amount_usd": 1000}],
    )

    shared = {s["dependency"]: s for s in exposure["shared_dependencies"]}
    assert "chainlink-price-feeds" in shared
    assert "chainlink-node-operators" in shared
    assert shared["chainlink-node-operators"]["share_pct"] == 100.0
    assert shared["chainlink-node-operators"]["paths"]["aave-v3"] == [
        "aave-v3", "chainlink-price-feeds", "chainlink-node-operators"
    ]
