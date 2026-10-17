"""Fixture graph on embedded FalkorDBLite (no Docker needed). It deliberately
includes traps: a test edge, an unverified edge, and RELATED_TO flagged eligible."""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

NOW = time.time()
DAY = 86400


def _e(**kw):
    base = {"verified": True, "risk_eligible": True, "is_test": False,
            "source_url": "https://example.org/src"}
    base.update(kw)
    return base


def _is_embedded(db):
    return type(db).__module__.startswith("redislite")


@pytest.fixture(scope="session")
def db(tmp_path_factory):
    try:
        from redislite.falkordb_client import FalkorDB
        return FalkorDB(str(tmp_path_factory.mktemp("fdb") / "t.db"))
    except (ImportError, ModuleNotFoundError):
        from falkordb import FalkorDB
        from risk_engine import config as C
        return FalkorDB(
            host=C.FALKORDB_HOST,
            port=C.FALKORDB_PORT,
            username=C.FALKORDB_USERNAME,
            password=C.FALKORDB_PASSWORD,
        )


def _protocol(slug, **kw):
    return {"slug": slug, "name": slug.title(), "category": "Lending", "tvl": 1e9,
            "change_7d": 1.0, "audits": 3, "age_days": 1000, **kw}


@pytest.fixture(scope="session")
def risk_graph(db):
    graph_name = "defi_risk" if _is_embedded(db) else "defi_risk_test"
    g = db.select_graph(graph_name)
    try:
        g.delete()
    except Exception:
        pass
    g = db.select_graph(graph_name)
    nodes = [
        ("Protocol", _protocol("aave")), ("Protocol", _protocol("compound")),
        ("Protocol", _protocol("lend3")), ("Protocol", _protocol("lonely")),
        ("Protocol", _protocol("young_fork", audits=0, age_days=30)),
        ("Protocol", _protocol("hacked", category="Bridge")),
        ("Protocol", _protocol("victim")), ("Protocol", _protocol("noaudit_data", audits=None)),
        ("Protocol", _protocol("falling", change_7d=-45.0)),
        ("Protocol", _protocol("algo_user")), ("Protocol", _protocol("depeg_user")),
        ("Protocol", _protocol("l2_user")),
        ("Oracle", {"slug": "chainlink", "name": "Chainlink"}),
        ("Oracle", {"slug": "node_op", "name": "Node Operator"}),
        ("Controller", {"slug": "eoa_admin", "name": "EOA admin", "controller_type": "eoa"}),
        ("Controller", {"slug": "msig2", "name": "2-of-5", "controller_type": "multisig",
                        "threshold": 2, "timelock_hours": 0}),
        ("Stablecoin", {"slug": "usdc", "name": "USDC", "price": 1.0, "pegType": "peggedUSD"}),
        ("Stablecoin", {"slug": "usdx", "name": "USDX", "pegMechanism": "algorithmic",
                        "price": 1.0, "pegType": "peggedUSD"}),
        ("Stablecoin", {"slug": "usdbad", "name": "USDBAD", "price": 0.9, "pegType": "peggedUSD"}),
        ("Protocol", _protocol("ghost")),
    ]
    for lab, props in nodes:
        g.query(f"CREATE (n:{lab}) SET n = $p", {"p": props})
    now_ms = int((NOW - 100 * DAY) * 1000)
    g.query("MATCH (p:Protocol {slug:'hacked'}) CREATE (p)-[:AFFECTED_BY]->(:Incident "
            "{name:'Bridge exploit', date:$d, amount:50000000})", {"d": now_ms})
    g.query("MATCH (p:Protocol {slug:'aave'}) CREATE (p)-[:AFFECTED_BY]->(:Incident "
            "{name:'old', date:$d, amount:1000})", {"d": int((NOW - 3000 * DAY) * 1000)})
    g.query("MATCH (p:Protocol {slug:'falling'}) CREATE (p)-[:HAS_POOL]->(:Pool "
            "{symbol:'X', apy:100, apyReward:90, outlier:true})")
    g.query("MATCH (p:Protocol {slug:'aave'}) CREATE (p)-[:DEPLOYED_ON]->(:Chain {slug:'ethereum'})")

    edges = [
        ("aave", "USES_ORACLE", "chainlink", _e()), ("compound", "USES_ORACLE", "chainlink", _e()),
        ("lend3", "USES_ORACLE", "chainlink", _e()),
        ("chainlink", "DEPENDS_ON", "node_op", _e()),
        ("young_fork", "GOVERNED_BY", "eoa_admin", _e()),
        ("aave", "GOVERNED_BY", "msig2", _e()),
        ("aave", "DEPENDS_ON", "usdc", _e()),
        ("hacked", "DEPENDS_ON", "usdx", _e()), ("algo_user", "DEPENDS_ON", "usdx", _e()),
        ("victim", "DEPENDS_ON", "hacked", _e()),
        ("depeg_user", "DEPENDS_ON", "usdbad", _e()),
        # traps
        ("compound", "DEPENDS_ON", "ghost", _e(is_test=True)),
        ("aave", "DEPENDS_ON", "usdx", _e(verified=False)),
        ("lonely", "DEPENDS_ON", "usdc", {"verified": True}),  # risk_eligible missing -> excluded
        ("aave", "RELATED_TO", "compound", _e()),
        ("l2_user", "DEPENDS_ON", "victim", _e(strength=0.5)),
    ]
    for a, t, b, props in edges:
        g.query(f"MATCH (a {{slug:$a}}), (b {{slug:$b}}) CREATE (a)-[r:{t}]->(b) SET r = $p",
                {"a": a, "b": b, "p": props})
    yield g
    if not _is_embedded(db):
        try:
            g.delete()
        except Exception:
            pass


@pytest.fixture(scope="session")
def evidence_graph(db):
    graph_name = "defi_evidence" if _is_embedded(db) else "defi_evidence_test"
    g = db.select_graph(graph_name)
    try:
        g.delete()
    except Exception:
        pass
    g = db.select_graph(graph_name)
    g.query("CREATE (:Evidence {id:'ev1', title:'Aave audit', url:'https://x/y', protocol_slug:'aave'})")
    yield g
    if not _is_embedded(db):
        try:
            g.delete()
        except Exception:
            pass


@pytest.fixture(scope="session")
def rg(db, risk_graph):
    from risk_engine import RiskGraph
    return RiskGraph(db, graph_name=risk_graph.name)


@pytest.fixture(scope="session")
def ev(db, evidence_graph):
    from risk_engine.evidence import EvidenceIndex
    return EvidenceIndex(db, graph_name=evidence_graph.name)
