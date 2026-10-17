import time

import pytest

from risk_engine import assess_proposal, portfolio_exposure, simulate_shock, systemic_importance
from risk_engine import gate
from risk_engine.propagation import pagerank

NOW = time.time()


def A(rg, proto, amt=1000, **kw):
    return assess_proposal({"protocol_id": proto, "amount_usd": amt}, rg=rg, now=NOW, **kw)


def rules(v):
    return {f["rule"] for f in v["findings"]}


def tags(v):
    return set(v["tags"])


# ---- eligibility (fail-closed) ------------------------------------------------
def test_test_edge_excluded(rg):
    r = simulate_shock(rg, "ghost")
    assert r["outcome"] == "no_modelled_dependents"


def test_unverified_edge_excluded(rg):
    r = simulate_shock(rg, "usdx")
    assert "aave" not in {a["node"] for a in r["affected"]}
    assert "hacked" in {a["node"] for a in r["affected"]}


def test_missing_eligibility_flag_excluded(rg):
    assert "lonely" not in {a["node"] for a in simulate_shock(rg, "usdc")["affected"]}


def test_related_to_never_carries_risk(rg):
    assert "aave" not in {a["node"] for a in simulate_shock(rg, "compound")["affected"]}


# ---- shock --------------------------------------------------------------------
def test_shock_multihop_and_strength(rg):
    r = simulate_shock(rg, "usdx", severity=1.0, max_hops=3)
    by = {a["node"]: a for a in r["affected"]}
    assert by["hacked"]["hops"] == 1 and by["victim"]["hops"] == 2 and by["l2_user"]["hops"] == 3
    assert by["victim"]["impact_fraction"] < by["hacked"]["impact_fraction"]
    assert by["l2_user"]["path"] == ["l2_user", "victim", "hacked", "usdx"]


def test_shock_hop_limit(rg):
    r = simulate_shock(rg, "usdx", max_hops=1)
    assert {a["node"] for a in r["affected"]} == {"hacked", "algo_user"}


def test_shock_unknown_node(rg):
    r = simulate_shock(rg, "chainlnk")
    assert r["outcome"] == "unknown_node" and "not modelled" in r["note"].lower()


def test_shock_positions_loss(rg):
    r = simulate_shock(rg, "chainlink", 1.0, 2, [{"protocol_id": "aave", "amount_usd": 1000}])
    assert r["estimated_total_loss_usd"] == 500.0


# ---- exposure / importance ------------------------------------------------------
def test_shared_oracle_exposure(rg):
    r = portfolio_exposure(rg, [{"protocol_id": "aave", "amount_usd": 500},
                                {"protocol_id": "compound", "amount_usd": 500}])
    d = {x["dependency"]: x for x in r["shared_dependencies"]}
    assert d["chainlink"]["share_pct"] == 100.0
    assert "ghost" not in d


def test_importance_and_pagerank(rg):
    r = systemic_importance(rg, "chainlink")
    assert set(r["direct_dependents"]) == {"aave", "compound", "lend3"}
    assert r["pagerank_rank"] is not None
    pr = pagerank([("a", "b"), ("c", "b")])
    assert pr["b"] > pr["a"]


# ---- assess: rules ---------------------------------------------------------------
def test_unknown_protocol_blocks_with_suggestion(rg):
    v = A(rg, "aav")
    assert v["outcome"] == "BLOCK" and v["reason"] == "unknown_protocol"
    assert any(d["key"] == "aave" for d in v["did_you_mean"])


def test_r1_concentration_caps(rg):
    v = A(rg, "lend3", 500, positions=[{"protocol_id": "aave", "amount_usd": 500},
                                       {"protocol_id": "compound", "amount_usd": 500}])
    f = next(f for f in v["findings"] if f["rule"] == "R1")
    assert v["outcome"] == "BLOCK" and f["cap_usd"] == 0.0 and v["allowed_amount_usd"] == 0.0
    assert "shared_dependency" in tags(v)
    assert f["path"][-1] == "chainlink"
    assert f["evidence"][0]["source_url"]


def test_r1_not_fired_when_diversified(rg):
    v = A(rg, "lend3", 100, positions=[{"protocol_id": "lonely", "amount_usd": 5000}], capital_usd=5100)
    assert "R1" not in rules(v)


def test_r2_young_unaudited(rg):
    v = A(rg, "young_fork", 1000, capital_usd=10000)
    assert {"unaudited_listed", "young_protocol"} <= tags(v)
    assert v["allowed_amount_usd"] == 500.0  # 5% of 10k


def test_r3_own_and_dependency_incident(rg):
    assert "recent_incident" in tags(A(rg, "hacked", 100, capital_usd=100000))
    v = A(rg, "victim", 100, capital_usd=100000)
    assert "dependency_incident" in tags(v)
    f = next(f for f in v["findings"] if f["rule"] == "R3")
    assert f["path"] == ["victim", "hacked"] and f["details"]["incidents"][0]["amount"] == 50000000


def test_old_incident_is_not_recent(rg):
    v = A(rg, "aave", 100, capital_usd=100000)
    assert "incident_history" in tags(v) and "recent_incident" not in tags(v)


def test_r4_algorithmic_and_depeg(rg):
    assert "algorithmic_stablecoin" in tags(A(rg, "algo_user", 100, capital_usd=100000))
    v = A(rg, "depeg_user", 100, capital_usd=100000)
    assert v["outcome"] == "BLOCK" and v["allowed_amount_usd"] == 0.0


def test_r5_controller(rg):
    assert "admin_eoa" in tags(A(rg, "young_fork", 10, capital_usd=100000))
    v = A(rg, "aave", 10, capital_usd=100000)
    assert {"weak_multisig", "no_timelock"} <= tags(v)


def test_r6_market(rg):
    v = A(rg, "falling", 100, capital_usd=100000)
    assert {"tvl_drop", "high_apy_outlier", "reward_driven_yield"} <= tags(v)


def test_r9_coverage_not_safe(rg):
    v = A(rg, "lonely", 100, capital_usd=100000)
    assert "no_verified_dependencies" in tags(v)
    assert v["outcome"] == "WARN" and "no verified dependencies modelled" in v["coverage"]["data_gaps"]
    assert "not safe" in v["findings"][0]["summary"]


def test_audit_missing_is_not_unaudited(rg):
    v = A(rg, "noaudit_data", 100, capital_usd=100000)
    assert "audit_data_missing" in tags(v) and "unaudited_listed" not in tags(v)


def test_tolerance_scales_caps(rg):
    c = A(rg, "young_fork", 1000, capital_usd=10000, prefs={"risk_tolerance": "conservative"})
    g = A(rg, "young_fork", 1000, capital_usd=10000, prefs={"risk_tolerance": "aggressive"})
    assert c["allowed_amount_usd"] == 250.0 and g["allowed_amount_usd"] == 750.0


# ---- memory + prefs + synthetic ----------------------------------------------------
def test_memory_rule_and_mistake_matched_by_tag(rg):
    v = A(rg, "young_fork", 1000, capital_usd=100000,
          memory_rules=[{"id": "r1", "tag": "young_protocol", "action": "block", "note": "no young protocols"}],
          mistakes=[{"id": "m1", "tag": "admin_eoa", "summary": "lost on a one-key admin"}])
    assert v["outcome"] == "BLOCK"
    refs = [f["memory_ref"] for f in v["findings"] if f["memory_ref"]]
    assert {r["id"] for r in refs} == {"r1", "m1"}


def test_memory_not_matched_when_tag_absent(rg):
    v = A(rg, "aave", 10, capital_usd=100000, memory_rules=[{"tag": "young_protocol", "action": "block"}])
    assert "R7" not in rules(v)


def test_prefs(rg):
    v = A(rg, "hacked", 100, capital_usd=100000, prefs={"avoid_categories": ["bridge"]})
    assert v["outcome"] == "BLOCK" and "R8" in rules(v)
    v = A(rg, "lend3", 5000, capital_usd=10000, prefs={"max_position_pct": 10})
    assert v["allowed_amount_usd"] <= 1000


def test_synthetic_shock_in_memory_only(rg):
    v = A(rg, "aave", 1000, capital_usd=100000, synthetic_shocks=[{"node": "chainlink", "severity": 1.0}])
    f = next(f for f in v["findings"] if f["rule"] == "S1")
    assert f["details"]["synthetic"] and f["details"]["estimated_loss_usd"] == 500.0
    assert simulate_shock(rg, "chainlink")["outcome"] == "ok"  # graph untouched
    n = rg.g.query("MATCH (n) WHERE n.synthetic = true RETURN count(n)").result_set[0][0]
    assert n == 0


def test_evidence_attached(rg, ev):
    v = A(rg, "aave", 10, capital_usd=100000, evidence=ev)
    assert any(e.get("kind") == "document" for f in v["findings"] for e in f["evidence"])


def test_deterministic(rg):
    a, b = A(rg, "aave", 10, capital_usd=100000), A(rg, "aave", 10, capital_usd=100000)
    assert a == b


# ---- gate ----------------------------------------------------------------------------
def test_gate(rg):
    v = A(rg, "young_fork", 1000, capital_usd=10000)
    t = gate.issue(v)
    assert t["issued"] and t["approved_amount_usd"] == 500.0
    assert gate.verify(t["token"], {"protocol_id": "young_fork", "amount_usd": 500})[0]
    assert not gate.verify(t["token"], {"protocol_id": "young_fork", "amount_usd": 1000})[0]
    assert not gate.verify(t["token"], {"protocol_id": "aave", "amount_usd": 100})[0]
    assert not gate.verify(t["token"] + "x", {"protocol_id": "young_fork", "amount_usd": 100})[0]
    assert not gate.verify(t["token"], {"protocol_id": "young_fork", "amount_usd": 100}, now=NOW + 999)[0]
    assert not gate.issue(A(rg, "depeg_user", 100, capital_usd=100000))["issued"]
