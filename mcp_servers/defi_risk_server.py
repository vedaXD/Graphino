"""MCP Server: defi-risk

FastMCP server exposing deterministic DeFi risk analytics, multi-hop dependency paths,
contagion simulation, and gated paper trading over the FalkorDB `defi_risk` and `defi_evidence` graphs.

ARCHITECTURAL PRINCIPLES:
1. The LLM never decides a risk verdict; verdicts are computed deterministically by `risk_engine.assess_proposal`.
2. Fail-closed: missing edges or unmodelled protocols mean 'not modelled', never 'safe'.
3. Action Gate: `execute_paper_trade` strictly enforces HMAC gate verification via `risk_engine.gate.verify`.
   `gate.issue` is intentionally NOT exposed to the LLM; tokens are issued only by the orchestrator.
4. Read-only to `defi_risk`: this server never mutates the underlying risk graph.

CONNECTING THE SECOND MCP SERVER (@falkordb/mcpserver):
The Bulwark architecture pairs this server with FalkorDB's official read-only MCP server
for ad-hoc Cypher queries, schema exploration, and graph introspection:
  - Docker:
      docker run -d --name falkordb-mcp -p 8000:8000 \\
        -e FALKORDB_HOST=localhost \\
        -e FALKORDB_PORT=6379 \\
        -e FALKORDB_DEFAULT_READONLY=true \\
        falkordb/mcpserver:latest
  - NPX:
      npx -y @falkordb/mcpserver --host localhost --port 6379 --readonly
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from typing import Any

from mcp.server.fastmcp import FastMCP

from risk_engine import RiskGraph, assess_proposal as _assess_proposal
from risk_engine import config as C
from risk_engine import gate
from risk_engine.evidence import EvidenceIndex
from risk_engine.propagation import (
    best_paths,
    path_strength,
    portfolio_exposure as _portfolio_exposure,
    simulate_shock as _simulate_shock,
    systemic_importance as _systemic_importance,
)

logger = logging.getLogger("defi_risk_server")

# Initialize FastMCP Server
mcp = FastMCP(
    "defi-risk",
    instructions="Deterministic DeFi Risk Guardian MCP Server on FalkorDB",
)

# Global lazily-initialized or eager graph handles
_rg: RiskGraph | None = None
_ev: EvidenceIndex | None = None
_paper_positions: list[dict] = []


def get_risk_graph() -> RiskGraph:
    global _rg
    if _rg is None:
        _rg = RiskGraph()
    return _rg


def get_evidence_index() -> EvidenceIndex:
    global _ev
    if _ev is None:
        _ev = EvidenceIndex()
    return _ev


@mcp.tool()
def search_protocol(query: str) -> dict:
    """Search and resolve a protocol by slug, name, or identifier in the FalkorDB risk graph.

    Args:
        query: Protocol slug, ID, or name (e.g., 'aave', 'aave-v3', 'lido', 'compound').

    Returns:
        JSON object containing resolution status:
        - If resolved: `found=True`, node key, labels, and properties.
        - If not resolved: `found=False`, and a list of `did_you_mean` suggestions.
          Absence from the graph indicates the protocol is unmodelled, NOT safe.
    """
    if not query or not query.strip():
        return {
            "found": False,
            "query": query,
            "error": "Query cannot be empty.",
            "did_you_mean": [],
        }

    rg = get_risk_graph()
    q = query.strip()
    node = rg.resolve(q, "Protocol")
    if node is not None:
        return {
            "found": True,
            "protocol_id": node["key"],
            "name": node["props"].get("name", node["key"]),
            "labels": node["labels"],
            "properties": node["props"],
        }

    # If direct resolution failed, search for fuzzy / contains suggestions
    suggestions = rg.did_you_mean(q)
    return {
        "found": False,
        "query": q,
        "did_you_mean": suggestions,
        "note": f"'{q}' is not found in the risk graph. Unmodelled protocols are treated as unknown, not safe.",
    }


@mcp.tool()
def get_protocol_profile(protocol_id: str) -> dict:
    """Retrieve full risk profile for a protocol from the graph.

    Fetches structured facts (TVL, 1d/7d changes, audits, age), deployed chains,
    recorded historical incidents, yield pools, and eligible multi-hop dependency
    paths with citation source URLs.

    Args:
        protocol_id: The protocol slug or key in the risk graph (e.g., 'aave-v3', 'lido').

    Returns:
        Full protocol profile dictionary with facts, incidents, chains, pools,
        and dependency paths with source URLs for audit and verification.
    """
    if not protocol_id or not protocol_id.strip():
        return {"found": False, "error": "protocol_id must be provided"}

    rg = get_risk_graph()
    ev = get_evidence_index()
    k = protocol_id.strip()

    node = rg.resolve(k, "Protocol")
    if node is None:
        return {
            "found": False,
            "protocol_id": k,
            "did_you_mean": rg.did_you_mean(k),
            "note": f"Protocol '{k}' is not in the risk graph. Absence means not modelled, not safe.",
        }

    facts = rg.protocol_facts(node, time.time())
    fwd = rg.forward_paths([facts.key], max_hops=C.TH["MAX_HOPS"])
    recs = best_paths(fwd.get(facts.key, []))

    dep_paths = []
    for dep_key, rec in recs.items():
        if dep_key == facts.key:
            continue
        dep_paths.append({
            "target": dep_key,
            "target_labels": rec.other_labels,
            "hops": rec.hops,
            "path": rec.nodes,
            "relationships": rec.rels,
            "strength": round(path_strength(rec), 4),
            "evidence": rec.edge_evidence(),
        })

    # Evidence documents linked to this protocol
    evidence_docs = ev.for_protocol(facts.key) if ev.available else []

    return {
        "found": True,
        "protocol_id": facts.key,
        "name": facts.name,
        "category": facts.category,
        "tvl_usd": facts.tvl,
        "change_1d": facts.change_1d,
        "change_7d": facts.change_7d,
        "audits": facts.audits,
        "age_days": round(facts.age_days, 1) if facts.age_days is not None else None,
        "chains": facts.chains,
        "incidents": facts.incidents,
        "pools": facts.pools,
        "dependency_paths": dep_paths,
        "evidence_documents": evidence_docs,
        "coverage_note": (
            "Profile reflects modelled graph data only. "
            + ("No verified dependencies modelled." if not dep_paths else f"{len(dep_paths)} verified dependency path(s) modelled.")
        ),
    }


@mcp.tool()
def simulate_shock(
    node: str,
    severity: float = 1.0,
    max_hops: int = 3,
    positions: list[dict] | None = None,
) -> dict:
    """Simulate hypothetical failure or shock propagation from a specific entity.

    Walks incoming dependency edges backwards to determine which protocols rely
    on the affected node (e.g., oracle compromise, stablecoin depeg, bridge exploit)
    and estimates contagion impact fractions and position dollar losses.

    Args:
        node: The entity slug undergoing a shock (e.g., 'chainlink-price-feeds', 'usdc').
        severity: Failure magnitude between 0.0 (no impact) and 1.0 (complete failure). Default 1.0.
        max_hops: Maximum dependency distance to walk (1 to 4). Default 3.
        positions: Optional current portfolio holdings `[{'protocol_id': 'aave', 'amount_usd': 500}]`.

    Returns:
        Contagion results including affected protocols, hops, estimated impact fractions,
        and total estimated portfolio loss.
    """
    rg = get_risk_graph()
    return _simulate_shock(
        rg=rg,
        node_key=node.strip(),
        severity=severity,
        max_hops=max_hops,
        positions=positions,
    )


@mcp.tool()
def portfolio_exposure(
    positions: list[dict],
    capital_usd: float | None = None,
) -> dict:
    """Analyze a multi-asset portfolio for hidden shared dependencies.

    Traverses up to 3 hops of eligible dependency edges to reveal shared infrastructure
    (common oracles, wrapped bridges, reserve assets, multisigs) across multiple holdings.

    Args:
        positions: List of holdings, each formatted as `{'protocol_id': 'slug', 'amount_usd': float}`.
        capital_usd: Optional total portfolio capital in USD. Defaults to sum of positions.

    Returns:
        Shared dependencies, percentage concentration of capital, dependency paths,
        and list of holdings lacking modelled dependencies.
    """
    if not positions:
        return {
            "capital_usd": capital_usd or 0.0,
            "shared_dependencies": [],
            "holdings_without_modelled_dependencies": [],
            "note": "No positions provided for exposure analysis.",
        }

    rg = get_risk_graph()
    return _portfolio_exposure(
        rg=rg,
        positions=positions,
        capital_usd=capital_usd,
    )


@mcp.tool()
def systemic_importance(node: str) -> dict:
    """Calculate systemic importance metrics and PageRank rank for an entity.

    Measures direct and transitive dependents over verified, risk-eligible edges
    and computes relative PageRank centrality over the entire graph structure.

    Args:
        node: Identifier or slug of the node (e.g., 'chainlink', 'lido-accounting-oracle').

    Returns:
        Metrics including direct_dependents, transitive_dependents count, PageRank score,
        and systemic rank.
    """
    rg = get_risk_graph()
    return _systemic_importance(
        rg=rg,
        node_key=node.strip(),
    )


@mcp.tool()
def assess_proposal(
    proposal: dict,
    positions: list[dict] | None = None,
    user_id: str | None = None,
    capital_usd: float | None = None,
) -> dict:
    """Deterministically assess a DeFi capital allocation proposal against risk rules.

    Applies deterministic rules R1-R9 (concentration, audit history, incidents,
    peg stability, multisig controllers, market liquidity, and personalized learned
    rules/mistakes).

    Args:
        proposal: Dict with `protocol_id` (str) and `amount_usd` (float), e.g., `{'protocol_id': 'aave-v3', 'amount_usd': 1000}`.
        positions: Existing portfolio positions `[{'protocol_id': 'slug', 'amount_usd': 500}]`.
        user_id: Optional user identifier. When supplied, loads that user's preferences,
                 learned rules, and past mistakes from the memory layer (`mem_<user_id>`).
        capital_usd: Optional total portfolio capital.

    Returns:
        Comprehensive risk assessment dict:
        - `outcome`: One of ALLOW, WARN, ALLOW_WITH_CAP, or BLOCK.
        - `allowed_amount_usd`: Maximum permitted allocation (0.0 if blocked).
        - `findings`: List of findings with rule ID, severity, summary, graph path, and evidence source URLs.
        - `tags`: Set of risk tags triggered.
        - `coverage`: Modelled status, dependency paths count, and data gaps.
    """
    rg = get_risk_graph()
    ev = get_evidence_index()

    prefs: dict[str, Any] = {}
    memory_rules: list[dict] = []
    mistakes: list[dict] = []

    # Attempt to load user memory if user_id is provided (integrated with Phase 2)
    if user_id:
        try:
            from memory import load_context
            mem_ctx = load_context(user_id)
            prefs = mem_ctx.get("prefs", {})
            memory_rules = mem_ctx.get("memory_rules", [])
            mistakes = mem_ctx.get("mistakes", [])
        except (ImportError, Exception):
            pass

    verdict = _assess_proposal(
        proposal=proposal,
        positions=positions,
        prefs=prefs,
        memory_rules=memory_rules,
        mistakes=mistakes,
        capital_usd=capital_usd,
        rg=rg,
        evidence=ev,
    )
    return verdict


@mcp.tool()
def execute_paper_trade(
    proposal: dict,
    gate_token: str,
    user_id: str = "default",
) -> dict:
    """Execute a paper trade allocation for an evaluated proposal.

    EXECUTOR-ONLY GATE TOOL: This tool enforces cryptographic HMAC verification.
    It requires an unexpired gate token issued by the orchestrator for a verdict
    that permits the exact proposal (protocol_id and amount_usd).

    If the gate token is invalid, expired, or does not match the proposal,
    execution is REFUSED immediately.

    Args:
        proposal: The trade details, e.g. `{'protocol_id': 'aave-v3', 'amount_usd': 500}`.
        gate_token: Cryptographically signed token issued by the orchestrator.
        user_id: The user account for the paper trade. Default 'default'.

    Returns:
        Execution confirmation with trade ID and status, or REFUSED response with reason.
    """
    now = time.time()
    valid, reason = gate.verify(gate_token, proposal, now=now)

    if not valid:
        return {
            "success": False,
            "status": "REFUSED",
            "reason": f"Gate verification failed: {reason}",
            "proposal": proposal,
            "message": "Paper trade execution was refused by the action gate. An orchestrator-signed HMAC token is required.",
        }

    # Generate unique deterministic paper trade ID
    proto = proposal.get("protocol_id", "unknown")
    amt = float(proposal.get("amount_usd", 0.0))
    raw_id = f"{user_id}:{proto}:{amt}:{gate_token[:16]}:{now}"
    trade_id = f"PT-{hashlib.sha256(raw_id.encode()).hexdigest()[:10]}"

    trade_record = {
        "trade_id": trade_id,
        "user_id": user_id,
        "protocol_id": proto,
        "amount_usd": amt,
        "chain": proposal.get("chain"),
        "timestamp": now,
        "status": "OPEN",
    }
    _paper_positions.append(trade_record)

    # If memory layer is available, record into user's memory graph
    try:
        from memory import record_paper_trade
        record_paper_trade(user_id, trade_record)
    except (ImportError, Exception):
        pass

    return {
        "success": True,
        "status": "EXECUTED",
        "trade": trade_record,
        "message": f"Paper trade executed: allocated ${amt:,.2f} to {proto}.",
    }


def main():
    """Run FastMCP server on stdio transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
