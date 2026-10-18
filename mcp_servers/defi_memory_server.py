"""MCP Server: defi-memory

FastMCP server managing per-user episodic, semantic, and procedural memory
in FalkorDB (`mem_<user_id>`).

TENANT ISOLATION:
Each user has an isolated graph (`mem_<user_id>`).
No cross-graph Cypher queries are performed.
The join to the risk graph happens purely via controlled risk tags (TAG_VOCABULARY).

TOOLS EXPOSED:
- load_context(user_id?)
- set_preference(key, value, user_id?)
- record_mistake(tag, summary, loss_usd, user_id?)
- promote_rule(mistake_id, action?, cap_pct?, note?, user_id?)
- list_rules(user_id?)
- forget(rule_id, user_id?)
- record_episode(proposal, verdict, decision, outcome?, session_id?, user_id?)
- get_portfolio(user_id?)
"""
from __future__ import annotations

import logging
import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from memory import (
    UserMemoryStore,
    forget as _forget,
    get_portfolio as _get_portfolio,
    list_rules as _list_rules,
    load_context as _load_context,
    promote_rule as _promote_rule,
    record_episode as _record_episode,
    record_mistake as _record_mistake,
    set_preference as _set_preference,
)

logger = logging.getLogger("defi_memory_server")

# Initialize FastMCP Server
mcp = FastMCP(
    "defi-memory",
    instructions="Personalized DeFi Memory & Past Mistakes Server on FalkorDB",
)


def _resolve_user(user_id: str | None = None) -> str:
    """Resolve user_id from parameter or fallback to server-side bound BULWARK_USER_ID."""
    if user_id and user_id.strip():
        return user_id.strip()
    return os.getenv("BULWARK_USER_ID", "default_user")


@mcp.tool()
def load_context(user_id: str | None = None) -> dict:
    """Load the user's complete active risk context (preferences, learned rules, and past mistakes).

    Returns data formatted in the exact dictionary structure accepted by `assess_proposal`.

    Args:
        user_id: Optional user identifier. Defaults to server-bound BULWARK_USER_ID.

    Returns:
        JSON object with keys:
        - `prefs`: dict of preferences (e.g. risk_tolerance, max_position_pct, avoid_categories).
        - `memory_rules`: list of active learned rules (tag, action, cap_pct, note).
        - `mistakes`: list of past mistakes with associated tags and historical losses.
    """
    uid = _resolve_user(user_id)
    return _load_context(uid)


@mcp.tool()
def set_preference(key: str, value: Any, user_id: str | None = None) -> dict:
    """Record or update a user preference (e.g. risk_tolerance, max_position_pct, avoid_categories).

    Args:
        key: Preference key (e.g. 'risk_tolerance', 'max_position_pct', 'avoid_categories', 'avoid_chains').
        value: The setting value (string, number, or list of strings).
        user_id: Optional user identifier.

    Returns:
        Confirmation dictionary with the updated preference.
    """
    uid = _resolve_user(user_id)
    return _set_preference(uid, key, value)


@mcp.tool()
def record_mistake(
    tag: str,
    summary: str,
    loss_usd: float = 0.0,
    user_id: str | None = None,
) -> dict:
    """Record a past DeFi mistake or loss associated with a controlled risk tag.

    The tag must belong to the controlled TAG_VOCABULARY (e.g., 'young_protocol', 'unaudited_listed',
    'admin_eoa', 'algorithmic_stablecoin', 'recent_incident', etc.).
    If the user has 2 or more mistakes with this tag, automatically returns a rule promotion suggestion.

    Args:
        tag: Risk tag from TAG_VOCABULARY.
        summary: Description of what went wrong or how the loss occurred.
        loss_usd: Estimated monetary loss in USD. Default 0.0.
        user_id: Optional user identifier.

    Returns:
        Dictionary with mistake ID, validated tag, summary, loss_usd, and optional promotion_suggestion.
    """
    uid = _resolve_user(user_id)
    return _record_mistake(uid, tag, summary, loss_usd)


@mcp.tool()
def promote_rule(
    mistake_id: str,
    action: str = "block",
    cap_pct: float | None = None,
    note: str | None = None,
    user_id: str | None = None,
) -> dict:
    """Promote a recorded mistake into an active LearnedRule.

    The promoted rule is stored in `mem_<user_id>` and will automatically trigger in
    `assess_proposal` (via rule R7) whenever future proposals carry the same risk tag.

    Args:
        mistake_id: The ID of the mistake being learned from (e.g., 'm_abc12345').
        action: Rule action to enforce: 'block', 'cap', or 'warn'. Default 'block'.
        cap_pct: Allocation cap percentage if action is 'cap' (e.g., 5.0).
        note: Explanation or guidance for why this rule exists.
        user_id: Optional user identifier.

    Returns:
        The created LearnedRule properties with active status.
    """
    uid = _resolve_user(user_id)
    return _promote_rule(uid, mistake_id, action, cap_pct, note)


@mcp.tool()
def list_rules(user_id: str | None = None) -> list[dict]:
    """List all currently active learned rules for this user.

    Args:
        user_id: Optional user identifier.

    Returns:
        List of rule dictionaries containing rule ID, tag, action, cap_pct, and note.
    """
    uid = _resolve_user(user_id)
    return _list_rules(uid)


@mcp.tool()
def forget(rule_id: str, user_id: str | None = None) -> dict:
    """Deactivate a learned rule so that it no longer restricts future proposals.

    Args:
        rule_id: The rule ID to deactivate (e.g., 'r_abc12345').
        user_id: Optional user identifier.

    Returns:
        Status indicating whether the rule was deactivated.
    """
    uid = _resolve_user(user_id)
    return _forget(uid, rule_id)


@mcp.tool()
def record_episode(
    proposal: dict,
    verdict: dict,
    decision: str,
    outcome: str = "",
    session_id: str | None = None,
    user_id: str | None = None,
) -> dict:
    """Record a complete interaction episode (proposal, risk verdict, user decision, and outcome).

    Args:
        proposal: The proposal evaluated `{'protocol_id': 'xyz', 'amount_usd': 1000}`.
        verdict: The verdict dictionary returned by `assess_proposal`.
        decision: User decision ('proceed', 'reject', 'adjusted_amount').
        outcome: Optional post-hoc notes or outcome summary.
        session_id: Optional current session identifier.
        user_id: Optional user identifier.

    Returns:
        Recorded episode summary with episode ID and timestamp.
    """
    uid = _resolve_user(user_id)
    return _record_episode(uid, proposal, verdict, decision, outcome, session_id)


@mcp.tool()
def get_portfolio(user_id: str | None = None) -> list[dict]:
    """Retrieve all open paper trading positions held by this user.

    Args:
        user_id: Optional user identifier.

    Returns:
        List of open positions `[{'trade_id': ..., 'protocol_id': ..., 'amount_usd': ...}]`.
    """
    uid = _resolve_user(user_id)
    return _get_portfolio(uid)


def main():
    """Run FastMCP memory server on stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
