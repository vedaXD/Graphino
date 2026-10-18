"""CLI bridge for frontend Next.js API to run Bulwark Deterministic Risk Engine & Gate Token
directly against live FalkorDB graph (defi_risk + mem_<user_id>).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Ensure root directory is on python path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

if sys.stdout.encoding != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from risk_engine.graph_view import RiskGraph
from risk_engine.engine import assess_proposal
from risk_engine import gate
from memory.store import UserMemoryStore


def main():
    parser = argparse.ArgumentParser(description="Bulwark Risk Assessment Bridge")
    parser.add_argument("--protocol", required=True, help="Protocol ID or slug (e.g. aave-v3)")
    parser.add_argument("--amount", type=float, required=True, help="Proposed allocation amount in USD")
    parser.add_argument("--user_id", default="demo_trader", help="Tenant user ID (e.g. demo_trader, alice, bob)")
    parser.add_argument("--tolerance", default="moderate", help="Risk tolerance (conservative, moderate, aggressive)")
    args = parser.parse_args()

    proposal = {
        "protocol_id": args.protocol,
        "amount_usd": args.amount,
    }

    try:
        # Load user context and paper portfolio positions from FalkorDB
        mem_store = UserMemoryStore(user_id=args.user_id)
        context = mem_store.load_context()
        portfolio = mem_store.get_portfolio()

        positions = [
            {"protocol_id": p["protocol_id"], "amount_usd": p["amount_usd"]}
            for p in portfolio
        ]

        prefs = context.get("prefs") or {}
        if args.tolerance:
            prefs["risk_tolerance"] = args.tolerance

        memory_rules = context.get("memory_rules") or []
        mistakes = context.get("mistakes") or []

        # Connect to FalkorDB risk graph
        rg = RiskGraph()

        # Execute deterministic risk engine
        verdict = assess_proposal(
            proposal=proposal,
            positions=positions,
            prefs=prefs,
            memory_rules=memory_rules,
            mistakes=mistakes,
            rg=rg,
        )

        # Issue HMAC Gate Token if permitted
        gate_token = gate.issue(verdict)

        output = {
            "success": True,
            "verdict": verdict,
            "gate_token": gate_token,
            "source": "falkordb_live",
        }
        print(json.dumps(output, default=str))

    except Exception as exc:
        print(
            json.dumps(
                {
                    "success": False,
                    "error": str(exc),
                    "proposal": proposal,
                }
            )
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
