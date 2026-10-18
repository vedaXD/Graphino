"""Tests for per-user memory graphs (mem_<user_id>).

Verifies:
1. Strict tag validation against TAG_VOCABULARY.
2. Preferences CRUD.
3. Mistakes recording and 2+ mistake auto-promotion suggestion.
4. Learned rules promotion, listing, and deactivation (forget).
5. Episodes and paper position tracking.
6. Tenant isolation between users.
7. CROSS-SESSION MEMORY: Session 1 records a mistake and promotes a rule,
   Session 2 (fresh objects) enforces BLOCK/CAP in assess_proposal,
   with the finding's memory_ref pointing directly at the rule.
"""
import uuid
import pytest

from memory import (
    UserMemoryStore,
    graph_name_for_user,
    load_context,
    promote_rule,
    record_mistake,
    set_preference,
    validate_tag,
)
from risk_engine import assess_proposal
from risk_engine import config as C


@pytest.fixture
def mem_store(db):
    uid = f"user_{uuid.uuid4().hex[:8]}"
    store = UserMemoryStore(user_id=uid, db=db)
    yield store
    # Clean up test user graph
    try:
        store.g.delete()
    except Exception:
        pass


def test_tag_validation():
    # Valid vocabulary tags must pass
    assert validate_tag("young_protocol") == "young_protocol"
    assert validate_tag("admin_eoa") == "admin_eoa"
    assert validate_tag("RECENT_INCIDENT") == "recent_incident"

    # Invalid tags must be strictly rejected
    with pytest.raises(ValueError, match="TAG_VOCABULARY"):
        validate_tag("made_up_tag")

    with pytest.raises(ValueError, match="TAG_VOCABULARY"):
        validate_tag("unverified_random_risk")


def test_preferences_crud(mem_store):
    mem_store.set_preference("risk_tolerance", "conservative")
    mem_store.set_preference("max_position_pct", 15.0)
    mem_store.set_preference("avoid_categories", ["Bridge", "Dex"])

    prefs = mem_store.get_preferences()
    assert prefs["risk_tolerance"] == "conservative"
    assert prefs["max_position_pct"] == 15.0
    assert prefs["avoid_categories"] == ["Bridge", "Dex"]


def test_record_mistake_and_auto_suggest(mem_store):
    # First mistake
    m1 = mem_store.record_mistake(
        tag="young_protocol",
        summary="Lost 5000 on a flash loan against a 3-week-old protocol",
        loss_usd=5000.0,
    )
    assert m1["tag"] == "young_protocol"
    assert m1["tag_mistake_count"] == 1
    assert m1["promotion_suggestion"] is None

    # Second mistake with same tag -> must auto-suggest promotion!
    m2 = mem_store.record_mistake(
        tag="young_protocol",
        summary="Lost another 6000 on a young fork with uninitialized proxy",
        loss_usd=6000.0,
    )
    assert m2["tag_mistake_count"] == 2
    suggestion = m2["promotion_suggestion"]
    assert suggestion is not None
    assert suggestion["tag"] == "young_protocol"
    assert suggestion["mistake_count"] == 2
    assert suggestion["suggested_action"] in ("block", "cap")


def test_promote_rule_and_list(mem_store):
    m = mem_store.record_mistake(
        tag="admin_eoa",
        summary="Admin key got drained, rugging all pool liquidity",
        loss_usd=25000.0,
    )
    # Promote to a BLOCK rule
    rule = mem_store.promote_rule(
        mistake_id=m["id"],
        action="block",
        note="Never allocate to EOA-controlled contracts",
    )
    assert rule["action"] == "block"
    assert rule["tag"] == "admin_eoa"
    assert rule["status"] == "active"

    rules = mem_store.list_rules(active_only=True)
    assert len(rules) == 1
    assert rules[0]["id"] == rule["id"]
    assert rules[0]["tag"] == "admin_eoa"
    assert rules[0]["action"] == "block"


def test_forget_rule(mem_store):
    m = mem_store.record_mistake(tag="single_oracle", summary="Stale oracle feed loss", loss_usd=2000.0)
    rule = mem_store.promote_rule(mistake_id=m["id"], action="cap", cap_pct=5.0)

    # Active before forget
    assert len(mem_store.list_rules(active_only=True)) == 1

    # Forget the rule
    res = mem_store.forget(rule["id"])
    assert res["deactivated"] is True

    # Inactive now
    assert len(mem_store.list_rules(active_only=True)) == 0


def test_record_episode_and_portfolio(mem_store):
    proposal = {"protocol_id": "aave", "amount_usd": 1000.0}
    verdict = {"outcome": "ALLOW", "allowed_amount_usd": 1000.0}

    ep = mem_store.record_episode(
        proposal=proposal,
        verdict=verdict,
        decision="proceed",
        outcome="Allocated without issue",
        session_id="sess_101",
    )
    assert ep["protocol_id"] == "aave"
    assert ep["decision"] == "proceed"

    # Record paper trade
    trade = {"protocol_id": "aave", "amount_usd": 1000.0, "chain": "ethereum"}
    t_res = mem_store.record_paper_trade(trade)
    assert t_res["status"] == "OPEN"

    portfolio = mem_store.get_portfolio()
    assert len(portfolio) == 1
    assert portfolio[0]["protocol_id"] == "aave"
    assert portfolio[0]["amount_usd"] == 1000.0


def test_user_tenant_isolation(db):
    uid_alice = f"alice_{uuid.uuid4().hex[:6]}"
    uid_bob = f"bob_{uuid.uuid4().hex[:6]}"

    store_alice = UserMemoryStore(user_id=uid_alice, db=db)
    store_bob = UserMemoryStore(user_id=uid_bob, db=db)

    try:
        store_alice.set_preference("risk_tolerance", "conservative")
        m = store_alice.record_mistake(tag="young_protocol", summary="Alice's loss", loss_usd=1000.0)
        store_alice.promote_rule(m["id"], action="block")

        # Bob's context must be completely empty (isolated graphs)
        bob_context = store_bob.load_context()
        assert bob_context["prefs"] == {}
        assert bob_context["memory_rules"] == []
        assert bob_context["mistakes"] == []

        alice_context = store_alice.load_context()
        assert alice_context["prefs"]["risk_tolerance"] == "conservative"
        assert len(alice_context["memory_rules"]) == 1
    finally:
        try:
            store_alice.g.delete()
        except Exception:
            pass
        try:
            store_bob.g.delete()
        except Exception:
            pass


def test_cross_session_rule_enforcement(db, rg):
    """CROSS-SESSION TEST:
    Session 1: User 'carol' records a mistake on 'young_protocol' and promotes a rule.
    Session 2 (fresh process objects): assess_proposal loads carol's memory context
    and produces BLOCK with memory_ref pointing directly to the promoted rule.
    """
    uid = f"carol_{uuid.uuid4().hex[:6]}"

    # ---- SESSION 1: Record mistake & promote rule ----
    session_1_store = UserMemoryStore(user_id=uid, db=db)
    mistake = session_1_store.record_mistake(
        tag="young_protocol",
        summary="Lost 10000 on a protocol listed for only 20 days",
        loss_usd=10000.0,
    )
    promoted_rule = session_1_store.promote_rule(
        mistake_id=mistake["id"],
        action="block",
        note="Strict block on young protocols under 90 days",
    )
    promoted_rule_id = promoted_rule["id"]

    # End Session 1 (discard session_1_store instance)
    del session_1_store

    # ---- SESSION 2: Fresh process objects simulate restart ----
    session_2_store = UserMemoryStore(user_id=uid, db=db)
    context = session_2_store.load_context()

    # Verify memory survived
    assert len(context["memory_rules"]) == 1
    assert context["memory_rules"][0]["id"] == promoted_rule_id

    # Evaluate 'young_fork' protocol (fixture protocol that triggers 'young_protocol' tag)
    verdict = assess_proposal(
        proposal={"protocol_id": "young_fork", "amount_usd": 1000.0},
        memory_rules=context["memory_rules"],
        mistakes=context["mistakes"],
        prefs=context["prefs"],
        capital_usd=10000.0,
        rg=rg,
    )

    try:
        # Rule R7 must fire and enforce BLOCK
        assert verdict["outcome"] == "BLOCK"
        assert verdict["allowed_amount_usd"] == 0.0

        # Finding must cite rule R7 and have memory_ref pointing to the promoted rule
        r7_findings = [f for f in verdict["findings"] if f["rule"] == "R7"]
        assert len(r7_findings) >= 1

        rule_finding = next(f for f in r7_findings if f["memory_ref"]["kind"] == "rule")
        assert rule_finding["memory_ref"]["id"] == promoted_rule_id
        assert rule_finding["memory_ref"]["tag"] == "young_protocol"
        assert "Strict block on young protocols" in rule_finding["summary"]
    finally:
        try:
            session_2_store.g.delete()
        except Exception:
            pass
