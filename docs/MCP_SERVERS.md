# Bulwark MCP Servers Architecture

Bulwark employs the Model Context Protocol (MCP) to provide agent roles with targeted, structured access to FalkorDB without giving LLMs unchecked or unvalidated access to graph internals.

## Server Catalog

| Server | Transport | Access Mode | Purpose |
|---|---|---|---|
| **`defi-risk`** | `stdio` | Domain-specific, read-only to risk graph + gated paper executor | Primary risk assessments, contagion shock simulation, systemic importance, and gate-verified execution. |
| **`@falkordb/mcpserver`** | `http` or `stdio` | Official FalkorDB server, **read-only** | Ad-hoc Cypher queries, schema introspection, and raw graph exploration. |
| **`defi-memory`** (Phase 2) | `stdio` | Per-user read/write (`mem_<user_id>`) | Episodic memory, learned rules from past mistakes, and preferences. |

---

## 1. Primary Server: `defi-risk`

The `defi-risk` server is built with the official Python MCP SDK using `FastMCP`.

### Starting the Server
```powershell
python -m mcp_servers.defi_risk_server
```

### Exposed Tools
1. **`search_protocol(query: str)`**:
   Resolves a protocol name or slug against `defi_risk`. Returns node details or `did_you_mean` fuzzy suggestions.
2. **`get_protocol_profile(protocol_id: str)`**:
   Returns protocol facts (TVL, audits, age), deployed chains, recorded historical incidents, and eligible multi-hop dependency paths with source URLs.
3. **`simulate_shock(node: str, severity: float = 1.0, max_hops: int = 3, positions: list[dict] | None = None)`**:
   Simulates hypothetical shock propagation backwards across dependency edges. Estimates contagion fraction and portfolio loss.
4. **`portfolio_exposure(positions: list[dict], capital_usd: float | None = None)`**:
   Identifies shared underlying dependencies (oracles, assets, bridges) across multiple portfolio holdings.
5. **`systemic_importance(node: str)`**:
   Computes direct and transitive dependents count, PageRank score, and systemic rank across the eligible dependency graph.
6. **`assess_proposal(proposal: dict, positions: list[dict] | None = None, user_id: str | None = None, capital_usd: float | None = None)`**:
   Runs the deterministic rule engine (R1-R9) against the proposal, incorporating user memory rules and past mistakes.
7. **`execute_paper_trade(proposal: dict, gate_token: str, user_id: str = "default")`**:
   **Executor-only gate tool**. Cryptographically verifies the HMAC gate token issued by the orchestrator. If the token is invalid, expired, or doesn't match the proposal, execution is refused immediately.

---

## 2. Second Server: `@falkordb/mcpserver` (Official Read-Only)

The official FalkorDB MCP server is used as a read-only secondary tool provider for ad-hoc Cypher queries and schema verification.

### Option A: Run via Docker (Recommended for production/containers)
```bash
docker run -d --name falkordb-mcp -p 8000:8000 \
  -e FALKORDB_HOST=localhost \
  -e FALKORDB_PORT=6379 \
  -e FALKORDB_DEFAULT_READONLY=true \
  falkordb/mcpserver:latest
```

### Option B: Run via NPX (Recommended for local dev)
```bash
npx -y @falkordb/mcpserver --host localhost --port 6379 --readonly
```

### Configuration in Agent Client / Claude Desktop / Bulwark Orchestrator
```json
{
  "mcpServers": {
    "defi-risk": {
      "command": ".venv/Scripts/python.exe",
      "args": ["-m", "mcp_servers.defi_risk_server"]
    },
    "falkordb-readonly": {
      "command": "npx",
      "args": ["-y", "@falkordb/mcpserver", "--host", "localhost", "--port", "6379", "--readonly"]
    }
  }
}
```

### Guardrails
- `FALKORDB_DEFAULT_READONLY=true`: Prevents mutations to the `defi_risk` graph through raw Cypher tools.
- All paper trades and allocations must proceed through the `defi-risk` action gate (`execute_paper_trade`).
