"""CLI bridge for frontend Next.js API to run Bulwark Python Orchestrator and Gemini LLM
with live FalkorDB graph context.
"""
from __future__ import annotations

import argparse
import json
import os
import re
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

from agents import Orchestrator
from risk_engine.db import connect
from google import genai


def extract_allocation_proposal(text: str) -> dict | None:
    """Detect if the user query is asking for an investment / allocation / proposal."""
    lower = text.lower()

    # Investment keywords
    action_words = [
        "invest", "allocation", "allocate", "deposit", "put", "stake",
        "lend", "supply", "trade", "execute", "buy", "borrow",
    ]
    is_action = any(w in lower for w in action_words)

    # Detect dollar amount
    amount = None
    amount_match = re.search(
        r"\$?\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|\d+)(?:\s*(k|thousand|m|million))?",
        lower,
        re.IGNORECASE,
    )
    if amount_match:
        try:
            num = float(amount_match.group(1).replace(",", ""))
            unit = amount_match.group(2)
            if unit:
                unit = unit.lower()
                if unit in ("k", "thousand"):
                    num *= 1000
                elif unit in ("m", "million"):
                    num *= 1000000
            if num > 0:
                amount = num
        except Exception:
            pass

    # Query live FalkorDB for matching protocols
    matched_id = None
    try:
        db = connect()
        g = db.select_graph("defi_risk")
        records = g.ro_query(
            "MATCH (p:Protocol) RETURN coalesce(p.slug, p.protocol_id), p.name"
        ).result_set
        for row in records:
            p_key, p_name = str(row[0]), str(row[1])
            # Check whole-word or partial match
            if p_name.lower() in lower or p_key.lower() in lower:
                matched_id = p_key
                break
    except Exception:
        pass

    if not matched_id:
        if "aave" in lower:
            matched_id = "aave-v3"
        elif "morpho" in lower:
            matched_id = "morpho-blue"
        elif "spark" in lower:
            matched_id = "sparklend"
        elif "euler" in lower:
            matched_id = "euler-v2"
        elif "lido" in lower:
            matched_id = "lido"
        elif "maple" in lower:
            matched_id = "maple"
        elif "justlend" in lower:
            matched_id = "justlend-v1"

    # If user explicitly asked an action AND protocol or amount was found
    if matched_id and (is_action or amount):
        return {"protocol_id": matched_id, "amount_usd": amount or 5000.0}

    return None


def answer_general_query_with_gemini(
    query: str, user_id: str = "demo_trader", graph_off: bool = False
) -> str:
    """Use Gemini 2.5 Flash with live FalkorDB graph context to answer conversational or analytical questions."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return "GEMINI_API_KEY is not configured in the environment."

    client = genai.Client(api_key=api_key)

    if graph_off:
        # Ungrounded baseline mode: no graph context
        prompt = f"""You are an ungrounded LLM baseline assistant without graph database access.
User query: "{query}"
Answer the question based only on general public knowledge. Note that graph tools are disabled."""
        models_to_try = [os.getenv("GEMINI_MODEL", "gemini-3.5-flash"), "gemini-3.5-flash-lite", "gemini-2.5-flash"]
        for m in models_to_try:
            try:
                resp = client.models.generate_content(
                    model=m,
                    contents=prompt,
                )
                if resp and resp.text:
                    return resp.text
            except Exception:
                continue
        return "Baseline LLM unable to generate response."

    # Fetch live verified context from FalkorDB
    context_sections = []
    try:
        db = connect()
        g_risk = db.select_graph("defi_risk")

        # 1. Top protocols
        proto_rows = g_risk.ro_query(
            "MATCH (p:Protocol) RETURN p.name, coalesce(p.tvl_usd, p.tvl), coalesce(p.audits, 0) ORDER BY coalesce(p.tvl_usd, p.tvl) DESC LIMIT 10"
        ).result_set
        proto_txt = "\n".join(
            f"- {r[0]}: TVL ${(float(r[1])/1e9):.2f}B, {r[2]} verified audits"
            for r in proto_rows if r[1]
        )
        context_sections.append(f"VERIFIED PROTOCOLS IN FALKORDB:\n{proto_txt}")

        # 2. Oracles & Dependencies
        oracle_rows = g_risk.ro_query(
            "MATCH (p:Protocol)-[:USES_ORACLE]->(o:Oracle) RETURN p.name, o.name"
        ).result_set
        oracle_txt = "\n".join(f"- {r[0]} relies on {r[1]}" for r in oracle_rows)
        context_sections.append(f"ORACLE DEPENDENCY RELATIONSHIPS:\n{oracle_txt}")

        # 3. Recorded Historical Incidents
        inc_rows = g_risk.ro_query(
            "MATCH (i:Incident) RETURN i.name, i.classification, i.amount_usd"
        ).result_set
        inc_txt = "\n".join(
            f"- {r[0]}: {r[1]} exploit, loss: ${float(r[2]):,.0f} USD"
            for r in inc_rows if r[2]
        )
        context_sections.append(f"HISTORICAL EXPLOIT INCIDENTS:\n{inc_txt}")

        # 4. User profile memory
        g_mem = db.select_graph(f"mem_{user_id}")
        user_rows = g_mem.ro_query(
            "MATCH (u:User)-[:HAS_PREFERENCE]->(pref) RETURN pref.key, pref.value"
        ).result_set
        pref_txt = ", ".join(f"{r[0]}={r[1]}" for r in user_rows)
        context_sections.append(f"TENANT USER MEMORY ({user_id}): {pref_txt or 'Balanced risk profile'}")

    except Exception as e:
        context_sections.append(f"Note: FalkorDB lookup partial ({e})")

    falkordb_knowledge = "\n\n".join(context_sections)

    system_instruction = (
        "You are the Bulwark Autonomous Risk & Investment Agent. "
        "You operate directly on top of FalkorDB knowledge graph (defi_risk, defi_evidence, and tenant memory). "
        "Answer the user's question directly, clearly, and concisely using the verified data provided. "
        "Format with clean GitHub markdown. Highlight protocol names, TVL, and risk findings. "
        "Remember: Absence of evidence in the graph is not evidence of safety."
    )

    prompt = f"""[VERIFIED FALKORDB GRAPH CONTEXT]
{falkordb_knowledge}

[USER QUESTION]
"{query}"

Please provide an intelligent, accurate response as the Bulwark Risk Agent:"""

    models_to_try = [os.getenv("GEMINI_MODEL", "gemini-3.5-flash"), "gemini-3.5-flash-lite", "gemini-2.5-flash"]
    for m in models_to_try:
        try:
            resp = client.models.generate_content(
                model=m,
                contents=prompt,
                config=dict(system_instruction=system_instruction, temperature=0.2),
            )
            if resp and resp.text:
                return resp.text
        except Exception:
            continue

    return "Graph evaluation completed. Unable to reach Gemini API at this time, but FalkorDB verified data is available in the dashboard."


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--message", type=str, default="")
    parser.add_argument("--protocol_id", type=str, default="")
    parser.add_argument("--amount_usd", type=float, default=0.0)
    parser.add_argument("--user_id", type=str, default="demo_trader")
    parser.add_argument("--graph_off", action="store_true")
    parser.add_argument("--execute", action="store_true")

    args = parser.parse_args()

    # Case 1: Explicit proposal arguments
    if args.protocol_id and args.amount_usd > 0:
        proposal = {"protocol_id": args.protocol_id, "amount_usd": args.amount_usd}
        orch = Orchestrator(user_id=args.user_id, graph_off=args.graph_off)
        result = orch.run_proposal(proposal, execute=args.execute)
        out = {
            "success": True,
            "task_id": result.get("task_id"),
            "proposal": proposal,
            "user_id": args.user_id,
            "verdict": result.get("verdict"),
            "gate_token": result.get("gate_token"),
            "trade_result": result.get("trade_result"),
            "explanation": result.get("explanation"),
            "baseline_note": result.get("baseline_note"),
            "abstention_active": result.get("abstention_active", False),
            "citations": result.get("citations", []),
            "graph_off": args.graph_off,
            "type": "proposal",
        }
        print(json.dumps(out))
        return

    # Case 2: Freeform message
    user_query = args.message.strip()
    proposal = extract_allocation_proposal(user_query)

    if proposal:
        # Run real Orchestrator for the proposal
        orch = Orchestrator(user_id=args.user_id, graph_off=args.graph_off)
        result = orch.run_proposal(proposal, execute=args.execute)
        out = {
            "success": True,
            "task_id": result.get("task_id"),
            "proposal": proposal,
            "user_id": args.user_id,
            "verdict": result.get("verdict"),
            "gate_token": result.get("gate_token"),
            "trade_result": result.get("trade_result"),
            "explanation": result.get("explanation"),
            "baseline_note": result.get("baseline_note"),
            "abstention_active": result.get("abstention_active", False),
            "citations": result.get("citations", []),
            "graph_off": args.graph_off,
            "type": "proposal",
        }
        print(json.dumps(out))
    else:
        # General query / inquiry / conversational question -> Answer with Gemini 2.5 Flash + FalkorDB context
        answer = answer_general_query_with_gemini(
            user_query, user_id=args.user_id, graph_off=args.graph_off
        )
        out = {
            "success": True,
            "task_id": f"task_query_{abs(hash(user_query)) % 100000}",
            "user_id": args.user_id,
            "explanation": answer,
            "text": answer,
            "graph_off": args.graph_off,
            "type": "conversational",
        }
        print(json.dumps(out))


if __name__ == "__main__":
    main()
