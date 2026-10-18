"""Demo and verification script for Bulwark Orchestrator and Agents.

Demonstrates:
1. Graph-On evaluation of a protocol proposal through Analyst -> Guardian -> Executor.
2. Citation validation and task coordination in FalkorDB.
3. Graph-Off baseline comparison (showing the ungrounded LLM response).
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Ensure root in path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from agents import Orchestrator


def main():
    print("=" * 70)
    print("BULWARK DEFI RISK GUARDIAN: AGENT ORCHESTRATION DEMO")
    print("=" * 70)

    user_id = "demo_trader"
    proposal = {"protocol_id": "aave-v3", "amount_usd": 1000.0}

    # 1. Run Graph-On Evaluation
    print(f"\n[1] Running GRAPH-ON evaluation for {proposal}...")
    orchestrator = Orchestrator(user_id=user_id)
    result = orchestrator.run_proposal(proposal, execute=True)

    print(f"    Task ID: {result['task_id']}")
    print(f"    Verdict Outcome: {result['verdict']['outcome']}")
    print(f"    Allowed Limit: ${result['verdict']['allowed_amount_usd']:,.2f}")
    print(f"    Gate Token Issued: {'YES (HMAC Signed)' if result['gate_token'] else 'NO'}")
    if result.get("trade_result"):
        print(f"    Trade Execution: {result['trade_result'].get('status')} (ID: {result['trade_result'].get('trade', {}).get('trade_id')})")
    print(f"    Abstention Active: {result['abstention_active']}")

    print("\n--- Guardian Explanation ---")
    print(result["explanation"])

    # 2. Run Graph-Off Baseline Comparison
    print("\n" + "=" * 70)
    print("[2] Running GRAPH-OFF BASELINE (no graph tools, ungrounded LLM)...")
    print("=" * 70)
    baseline_orch = Orchestrator(user_id=user_id, graph_off=True)
    baseline_result = baseline_orch.run_proposal(proposal)

    print("--- Baseline Response (Graph-Off) ---")
    print(baseline_result["explanation"])
    print(f"\nNote: {baseline_result.get('baseline_note')}")
    print("=" * 70)


if __name__ == "__main__":
    main()
