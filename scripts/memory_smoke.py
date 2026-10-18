"""Smoke test script for defi-memory MCP server.

Starts the defi-memory FastMCP server as an stdio subprocess, lists tools,
and exercises the memory lifecycle: preferences, mistake recording, rule promotion,
context loading, and forgetting rules.
"""
import asyncio
import json
import os
import sys
import uuid
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

EXPECTED_MEMORY_TOOLS = {
    "load_context",
    "set_preference",
    "record_mistake",
    "promote_rule",
    "list_rules",
    "forget",
    "record_episode",
    "get_portfolio",
}


def _parse_content(res) -> dict | list:
    if hasattr(res, "content") and res.content:
        first = res.content[0]
        if hasattr(first, "text"):
            try:
                return json.loads(first.text)
            except Exception:
                return {"raw_text": first.text}
    return {}


async def run_memory_smoke():
    print("=" * 60)
    print("Starting defi-memory MCP server smoke test...")
    print("=" * 60)

    test_user = f"smoke_user_{uuid.uuid4().hex[:6]}"
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_servers.defi_memory_server"],
        env={**os.environ, "PYTHONPATH": str(ROOT), "BULWARK_USER_ID": test_user},
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("[1] Session initialized successfully.")

            # 1. List tools
            tools_result = await session.list_tools()
            tool_names = {t.name for t in tools_result.tools}
            print(f"[2] Discovered {len(tool_names)} memory tools:")
            for t in sorted(tool_names):
                print(f"    - {t}")

            missing = EXPECTED_MEMORY_TOOLS - tool_names
            if missing:
                raise AssertionError(f"Missing memory tools: {missing}")
            print("    -> All expected memory tools registered.")

            # 2. Set preference
            print("\n[3] Calling set_preference(risk_tolerance='conservative')...")
            pref_res = await session.call_tool("set_preference", {
                "key": "risk_tolerance",
                "value": "conservative",
                "user_id": test_user,
            })
            pref_data = _parse_content(pref_res)
            print(f"    Result: {pref_data}")
            assert pref_data.get("key") == "risk_tolerance"
            print("    -> Preference set successfully.")

            # 3. Record mistake
            print("\n[4] Calling record_mistake(tag='young_protocol', loss=4000)...")
            mistake_res = await session.call_tool("record_mistake", {
                "tag": "young_protocol",
                "summary": "Lost 4000 on fresh protocol exploit",
                "loss_usd": 4000.0,
                "user_id": test_user,
            })
            mistake_data = _parse_content(mistake_res)
            print(f"    Result: mistake_id={mistake_data.get('id')}, tag={mistake_data.get('tag')}")
            mistake_id = mistake_data.get("id")
            assert mistake_id is not None
            print("    -> Mistake recorded successfully.")

            # 4. Promote rule
            print(f"\n[5] Calling promote_rule(mistake_id='{mistake_id}', action='block')...")
            rule_res = await session.call_tool("promote_rule", {
                "mistake_id": mistake_id,
                "action": "block",
                "note": "Never touch young protocols",
                "user_id": test_user,
            })
            rule_data = _parse_content(rule_res)
            print(f"    Result: rule_id={rule_data.get('id')}, action={rule_data.get('action')}")
            rule_id = rule_data.get("id")
            assert rule_id is not None
            assert rule_data.get("action") == "block"
            print("    -> Rule promoted successfully.")

            # 5. Load context
            print("\n[6] Calling load_context()...")
            ctx_res = await session.call_tool("load_context", {"user_id": test_user})
            ctx_data = _parse_content(ctx_res)
            rules = ctx_data.get("memory_rules", [])
            prefs = ctx_data.get("prefs", {})
            print(f"    Result: {len(rules)} active rule(s), prefs={prefs}")
            assert len(rules) == 1
            assert rules[0]["id"] == rule_id
            assert prefs.get("risk_tolerance") == "conservative"
            print("    -> Context loaded in exact assess_proposal format.")

            # 6. Forget rule
            print(f"\n[7] Calling forget(rule_id='{rule_id}')...")
            forget_res = await session.call_tool("forget", {"rule_id": rule_id, "user_id": test_user})
            forget_data = _parse_content(forget_res)
            print(f"    Result: {forget_data}")
            assert forget_data.get("deactivated") is True

            # Verify rules are now empty
            list_res = await session.call_tool("list_rules", {"user_id": test_user})
            active_rules = _parse_content(list_res)
            print(f"    Active rules after forget: {len(active_rules)}")
            assert len(active_rules) == 0
            print("    -> Rule successfully deactivated.")

    # Clean up test user graph in FalkorDB
    from memory import UserMemoryStore
    try:
        store = UserMemoryStore(user_id=test_user)
        store.g.delete()
    except Exception:
        pass

    print("\n" + "=" * 60)
    print("ALL DEFI-MEMORY MCP SMOKE CHECKS PASSED SUCCESSFULLY!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_memory_smoke())
