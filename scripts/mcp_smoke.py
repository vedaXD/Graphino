"""Smoke test script for defi-risk MCP server.

Starts the server as an stdio subprocess, lists its tools, verifies the
contract, and calls multiple tools (including the gate check).
"""
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Ensure workspace root is in path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from risk_engine import gate

EXPECTED_TOOLS = {
    "search_protocol",
    "get_protocol_profile",
    "simulate_shock",
    "portfolio_exposure",
    "systemic_importance",
    "assess_proposal",
    "execute_paper_trade",
}


def _parse_content(res) -> dict:
    """Helper to extract JSON dict from MCP tool result."""
    if hasattr(res, "content") and res.content:
        first = res.content[0]
        if hasattr(first, "text"):
            try:
                return json.loads(first.text)
            except Exception:
                return {"raw_text": first.text}
    return {}


async def run_smoke_test():
    print("=" * 60)
    print("Starting defi-risk MCP server smoke test...")
    print("=" * 60)

    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_servers.defi_risk_server"],
        env={**os.environ, "PYTHONPATH": str(ROOT)},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("[1] Session initialized successfully.")

            # Step 1: List tools
            tools_result = await session.list_tools()
            tool_names = {t.name for t in tools_result.tools}
            print(f"[2] Discovered {len(tool_names)} tools:")
            for t in sorted(tool_names):
                print(f"    - {t}")

            missing = EXPECTED_TOOLS - tool_names
            if missing:
                raise AssertionError(f"Missing expected tools: {missing}")
            print("    -> All expected tools are registered.")

            # Step 2: Call search_protocol
            print("\n[3] Calling tool: search_protocol(query='aave-v3')...")
            search_res = await session.call_tool("search_protocol", {"query": "aave-v3"})
            search_data = _parse_content(search_res)
            print(f"    Result: found={search_data.get('found')}, name={search_data.get('name')}")
            assert search_data.get("found") is True, f"search_protocol failed: {search_data}"
            print("    -> search_protocol test passed.")

            # Step 3: Call get_protocol_profile
            print("\n[4] Calling tool: get_protocol_profile(protocol_id='aave-v3')...")
            profile_res = await session.call_tool("get_protocol_profile", {"protocol_id": "aave-v3"})
            profile_data = _parse_content(profile_res)
            print(f"    Result: category={profile_data.get('category')}, TVL={profile_data.get('tvl_usd')}, "
                  f"incidents={len(profile_data.get('incidents', []))}")
            assert profile_data.get("found") is True, f"get_protocol_profile failed: {profile_data}"
            print("    -> get_protocol_profile test passed.")

            # Step 4: Call assess_proposal
            print("\n[5] Calling tool: assess_proposal(protocol='aave-v3', amount=1000)...")
            proposal = {"protocol_id": "aave-v3", "amount_usd": 1000.0}
            assess_res = await session.call_tool("assess_proposal", {"proposal": proposal})
            assess_data = _parse_content(assess_res)
            outcome = assess_data.get("outcome")
            allowed = assess_data.get("allowed_amount_usd")
            print(f"    Result: outcome={outcome}, allowed_amount_usd={allowed}")
            assert outcome in ("ALLOW", "WARN", "ALLOW_WITH_CAP", "BLOCK")
            print("    -> assess_proposal test passed.")

            # Step 5: Test Executor-only tool execute_paper_trade
            print("\n[6] Testing execute_paper_trade action gate...")
            # 5a. Call with invalid / fake token -> must be refused!
            refused_res = await session.call_tool(
                "execute_paper_trade",
                {"proposal": proposal, "gate_token": "invalid-token-12345"}
            )
            refused_data = _parse_content(refused_res)
            print(f"    Invalid token result: success={refused_data.get('success')}, status={refused_data.get('status')}")
            assert refused_data.get("success") is False
            assert refused_data.get("status") == "REFUSED"
            print("    -> Invalid token correctly refused.")

            # 5b. Issue a legitimate gate token and call execute_paper_trade
            gate_ticket = gate.issue(assess_data)
            if gate_ticket["issued"]:
                token = gate_ticket["token"]
                approved_amt = gate_ticket["approved_amount_usd"]
                valid_proposal = {"protocol_id": "aave-v3", "amount_usd": approved_amt}
                exec_res = await session.call_tool(
                    "execute_paper_trade",
                    {"proposal": valid_proposal, "gate_token": token}
                )
                exec_data = _parse_content(exec_res)
                print(f"    Valid token result: success={exec_data.get('success')}, status={exec_data.get('status')}, "
                      f"trade_id={exec_data.get('trade', {}).get('trade_id')}")
                assert exec_data.get("success") is True
                assert exec_data.get("status") == "EXECUTED"
                print("    -> Valid token correctly executed.")

    print("\n" + "=" * 60)
    print("ALL MCP SMOKE CHECKS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_smoke_test())
