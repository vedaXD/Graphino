"""Tests for Bulwark Multi-Agent Orchestrator, Roles, and Validator.

Verifies:
1. (a) The executor is refused without a token (or when verdict is BLOCK).
2. (b) An unknown protocol produces BLOCK with did_you_mean and NEVER reaches the executor.
3. (c) The citation validator rejects a fabricated number/URL and falls back to deterministic template.
4. Task handoff coordination through the user's memory graph.
5. The --graph-off flag produces ungrounded baseline comparison with tools disabled.
"""
import uuid
import pytest

from agents import (
    AgentMessage,
    Orchestrator,
    StubLLMClient,
    validate_citations,
)
from memory import UserMemoryStore


@pytest.fixture
def test_user(db):
    uid = f"agent_user_{uuid.uuid4().hex[:8]}"
    store = UserMemoryStore(user_id=uid, db=db)
    yield uid, store
    try:
        store.g.delete()
    except Exception:
        pass


def test_executor_refused_without_valid_token(test_user, db):
    """Check (a): The executor is refused without a token, and a BLOCK verdict never issues a token."""
    uid, store = test_user

    # young_fork with capital=10000 has audits=0 and age=30 -> rule R2 caps it
    # depeg_user has USD bad which is off-peg -> rule R4 blocks it
    stub_llm = StubLLMClient(
        responses=[
            AgentMessage(role="assistant", content="Evaluating depeg_user. This protocol uses an off-peg coin."),
        ]
    )

    orchestrator = Orchestrator(user_id=uid, llm_client=stub_llm, db=db)
    result = orchestrator.run_proposal(
        proposal={"protocol_id": "depeg_user", "amount_usd": 1000.0},
        execute=True,  # User asks to execute
    )

    # 1. Verdict is BLOCK
    assert result["verdict"]["outcome"] == "BLOCK"
    # 2. Gate token is NOT issued
    assert result["gate_token"] is None
    # 3. Trade result is None (never executed)
    assert result["trade_result"] is None

    # 4. Task status in memory graph is 'blocked'
    tasks = store.list_tasks()
    assert len(tasks) >= 1
    assert tasks[0]["status"] == "blocked"


def test_unknown_protocol_never_reaches_executor(test_user, db):
    """Check (b): An unknown protocol produces BLOCK with did_you_mean and never reaches the executor."""
    uid, store = test_user

    stub_llm = StubLLMClient(
        responses=[
            AgentMessage(role="assistant", content="Unknown protocol attempted."),
        ]
    )

    orchestrator = Orchestrator(user_id=uid, llm_client=stub_llm, db=db)
    result = orchestrator.run_proposal(
        proposal={"protocol_id": "totally_unknown_protocol_xyz", "amount_usd": 500.0},
        execute=True,
    )

    # Must be BLOCK with unknown_protocol
    assert result["verdict"]["outcome"] == "BLOCK"
    assert result["verdict"]["reason"] == "unknown_protocol"
    assert result["verdict"]["allowed_amount_usd"] == 0.0

    # Gate token is NOT issued
    assert result["gate_token"] is None
    assert result["trade_result"] is None

    # Abstention active
    assert result["abstention_active"] is True
    assert "not modelled" in result["explanation"].lower() or "abstention" in result["explanation"].lower()


def test_validator_rejects_fabricated_number(test_user, db):
    """Check (c): The citation validator rejects a fabricated number and falls back to deterministic template."""
    uid, store = test_user

    # LLM fabricates a fake number ($987,654) and fake URL
    hallucinated_text = (
        "I evaluated Aave V3. You can safely invest $987,654 into this protocol. "
        "Verified by audit at https://fake-audits-example.org/totally-fake-audit"
    )

    stub_llm = StubLLMClient(
        responses=[
            AgentMessage(role="assistant", content=hallucinated_text),
            AgentMessage(role="assistant", content=hallucinated_text),  # Retry also hallucinates
        ]
    )

    orchestrator = Orchestrator(user_id=uid, llm_client=stub_llm, db=db)
    result = orchestrator.run_proposal(
        proposal={"protocol_id": "aave-v3", "amount_usd": 1000.0},
    )

    # The validator must have caught the violations
    assert len(result["violations_corrected"]) > 0
    assert any("987,654" in v or "fake-audits" in v for v in result["violations_corrected"])

    # Fallback template was activated
    explanation = result["explanation"]
    assert "### Risk Verdict:" in explanation
    assert "Aave V3" in explanation
    assert "$987,654" not in explanation  # Fabricated number removed!


def test_task_handoff_coordination(test_user, db):
    """Verify agent coordination happens through Task nodes in the user's memory graph."""
    uid, store = test_user

    stub_llm = StubLLMClient(
        responses=[
            AgentMessage(role="assistant", content="Analysis and assessment complete."),
        ]
    )

    orchestrator = Orchestrator(user_id=uid, llm_client=stub_llm, db=db)
    result = orchestrator.run_proposal(
        proposal={"protocol_id": "aave-v3", "amount_usd": 50.0},
        execute=True,
    )

    task_id = result["task_id"]
    task = store.get_task(task_id)
    assert task is not None
    # Allowed with cap or executed
    assert task["status"] in ("executed", "evaluated")
    assert task["proposal"]["protocol_id"] == "aave-v3"


def test_graph_off_baseline_mode(test_user, db):
    """Verify --graph-off disables graph tools and returns the ungrounded baseline comparison."""
    uid, store = test_user

    stub_llm = StubLLMClient(
        responses=[
            AgentMessage(role="assistant", content="From general knowledge, Aave is a lending protocol."),
        ]
    )

    orchestrator = Orchestrator(user_id=uid, llm_client=stub_llm, graph_off=True, db=db)
    result = orchestrator.run_proposal(
        proposal={"protocol_id": "aave-v3", "amount_usd": 1000.0},
    )

    assert result["graph_off"] is True
    assert result["verdict"] is None
    assert result["gate_token"] is None
    assert "Graph tools disabled" in result["baseline_note"]
