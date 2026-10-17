# Bulwark: a memory-equipped DeFi risk guardian on FalkorDB

> Tracks entered: **Track 1 (Agents That Act on Connected Data)** and **Track 2 (Agent Memory and Coordination)**.

---

## 0. How to read this document

Sections follow the **build order**. Your earlier questions are answered at the point where you'd hit them while building:

| Question | Answered in |
|---|---|
| What's the problem statement? | §1 |
| Can we reuse code-graph / open-source / FalkorDB projects? | §2 |
| How do we create the graph model the best way? | §4 |
| Do we need GraphRAG-SDK, and how do we use it? | §5 |
| How is risk assessed and managed? | §6 |
| How do LLMs use tools and call MCP servers? | §7 |
| How is personalized memory created, stored, and where do past errors live? | §8 |
| Do users get separate graphs? | §3 (decision D3) and §8 |
| How do the agent and memory layers sit on the graph? | §3 (architecture) and §9 |
| How do we show memory across sessions and demo each objective? | §12 |

**Rules of the road (from the hackathon rules, don't violate):**
- The graph must do real work. If the product still works with FalkorDB removed, it's decoration. We prove it with a graph-off test (§12).
- Only **public, synthetic, or our own** data. No private, login-protected, paywalled, or personal data. No real wallets, no real funds.
- Main coding starts after the event started. Open-source libraries are fine; the *original work* is what's judged.
- Disclose AI coding assistant use in the README. Every teammate must be able to explain the graph model and queries.
- The submission must include: public repo, README with setup **and graph data model**, the **Cypher queries/graph algorithms the product depends on**, demo video, live deployment or full local setup, and the tracks entered.

---

## 1. Problem statement

**Retail DeFi users lose money in two predictable ways: they can't see how protocols are secretly connected, and they repeat their own mistakes.**

Today's tools show each protocol in isolation: a TVL number, an APY, maybe an audit badge. But the risks that actually wipe people out are *relational*: three "different" protocols that all depend on the same price oracle, a wrapped asset whose bridge was exploited, a stablecoin that quietly backs half your positions, an admin multisig shared across protocols that look unrelated. Generic AI assistants make it worse: they answer confidently from stale web text, can't show *why* they said something, and forget you tomorrow.

**Bulwark gives an AI agent a graph to reason over and a memory of you.**

1. A **risk graph** (FalkorDB) of protocols, chains, assets, oracles, bridges, controllers, auditors, and past incidents, connected by typed dependency edges. The agent follows connections (multi-hop), runs graph algorithms as tools, and every verdict comes with the **path** that justifies it.
2. A **grounded evidence layer** (GraphRAG-SDK on FalkorDB) over audit findings and incident post-mortems, with provenance back to source chunks and **abstention** when evidence is missing.
3. A **per-user memory graph** holding preferences (semantic), past decisions and outcomes (episodic), and learned rules from past mistakes (procedural). Memory **changes decisions**, not just chat tone: a mistake you made last month raises a finding on a similar protocol today.
4. An **action gate**: the agent can only open a (paper-traded) position if the graph-derived verdict allows it. The server enforces this, not the prompt.

**One-line pitch:** *"An agent that tells you what could break your DeFi portfolio, proves it with a path through a graph, and remembers what went wrong last time."*

**Non-goals:** real transactions or custody, a single opaque 0-100 "safety score", price prediction, yield maximization. We are a *risk guardian*, not a trading bot. Show a visible "not financial advice; paper trading only" banner.

---

## 2. Reuse map: what exists vs. what we build

**Principle:** use open-source pieces as *libraries and infrastructure*; the **domain graph model, dependency data, risk engine, memory schema, MCP tools, and agents are new work** (that's what's judged).

| Thing | Use? | How |
|---|---|---|
| **FalkorDB** (Docker `falkordb/falkordb:latest`, ports 6379 + 3000 for FalkorDB Browser) | Yes, core | Risk graph, evidence graph, per-user memory graphs |
| **falkordb-py** (`pip install FalkorDB`; async in `falkordb.asyncio`) | Yes, core | All app queries. Use parameters (`params=`), never string-concat |
| **FalkorDBLite** (`pip install falkordblite`, embedded) | Yes, tests/CI | Run unit tests with no Docker |
| **GraphRAG-SDK** (`pip install graphrag-sdk[litellm]`) | Yes, scoped | Evidence layer only (§5). Not for structured market data |
| **FalkorDB MCP server** (`npx -y @falkordb/mcpserver` or Docker `falkordb/mcpserver`, MIT) | Yes | Run it **read-only** against the risk graph as a generic "escape hatch" server so the agent has a real tool-selection decision (§7). Env: `FALKORDB_DEFAULT_READONLY=true`, `MCP_TRANSPORT=http`, `MCP_API_KEY=...` |
| **FalkorDB Browser** (included in the image, port 3000) | Yes, demo | Show the live graph and the user memory graphs |
| **mem0-falkordb** / **Graphiti (+ Graphiti MCP server)** | **No as core**, optional | They auto-extract memory with LLMs. Our differentiator is a *typed* join between past mistakes and risk tags, which needs a schema we control (§8). Don't run both. If we have spare time, Graphiti/Mem0 can back *free-text chat recall* only |
| **FalkorDB/code-graph** | **Patterns only, no code** | It's built for source code (Python/Java/C# analyzers). Steal the *shape*: its MCP tools `impact_analysis` / `find_path` / `get_neighbors` map to our `simulate_shock` / path explanation / dependency lookups, and its CLI + agent-guidance-file idea. Forking it as our base would blur the "new work" rule and add nothing for DeFi |
| **DeFiLlama free API** (`https://api.llama.fi`) | Yes, data | Protocols + TVL, chains, stablecoins (+ chain circulation), yield pools, fees. Free tier needs no key. **Verify endpoint hosts and response shapes on first call** (the docs list everything under `api.llama.fi`, but historically some groups lived on sub-hosts). Check DeFiLlama's attribution terms and credit them in the README |
| **L2BEAT** | Taxonomy only | Borrow its risk *categories* (state validation, data availability, exit window, sequencer failure, proposer failure) as property names on L2/bridge nodes. Don't depend on a scraped/unstable API; hand-enter a handful of fields with source URLs |
| Hacks/exploits dataset, oracle usage, bridge dependencies, admin controls | **We curate by hand** | The free DeFiLlama endpoints we read don't cover these. Curate from public docs/post-mortems into `data/seed/*.yaml` with a `source_url` on every edge (§4.3) |

---

## 3. Architecture and decisions

### 3.1 Decisions (locked; change only with a team decision)

- **D1. Python everywhere** (falkordb-py, graphrag-sdk, MCP Python SDK, one LLM client via LiteLLM). One language = agents can work in any module.
- **D2. Three graphs in one FalkorDB instance:**
  - `defi_risk`: shared, **read-only to agents**. Structured world knowledge + precomputed algorithm scores.
  - `defi_evidence`: written by GraphRAG-SDK. Unstructured evidence + provenance. Linked to `defi_risk` by `protocol_id` (application-layer join).
  - `mem_<user_id>`: **one graph per user**: memory, portfolio, chat history, task board.
- **D3. Separate graph per user, yes.** Tenant isolation by construction (no `WHERE user_id = ...` filters to forget), `DROP` graph = delete my data, and it's the FalkorDB multi-graph story the brief highlights ("separate memory per user or tenant").
- **D4. No cross-graph Cypher.** Treat cross-graph queries as unsupported (assumption; verify). Joins happen in the application layer through **shared string keys**: `protocol_id` and the controlled **tag vocabulary** (§4.4). A memory-to-risk lookup is always two cheap reads.
- **D5. The LLM never decides the tenant.** `user_id` is bound server-side (env var for a stdio MCP subprocess per session, or auth header for HTTP). Tools never take `user_id` from model output.
- **D6. Verdicts come from a deterministic rule engine over graph facts**, not from the LLM. The LLM picks tools and *narrates* the findings. Every claim in the final answer must cite a `finding_id` the tools returned (validated in code, §7.4).
- **D7. The action gate lives in the MCP server.** `open_position` refuses unless a fresh `assess_proposal` verdict allows it.
- **D8. Demo-stable data.** Freeze API pulls into `data/snapshots/` and commit them. The demo must not depend on a live API.
- **D9. Custom typed memory graph**, not an auto-extraction library (see §2).

### 3.2 Architecture

```
                  ┌──────────────────────────────────────────────────────────┐
 User (Streamlit) │  Orchestrator (task-board state machine, deterministic)   │
   chat + graph   │   Analyst agent ─► Guardian agent ─► Executor agent       │
   panel + trace  │   (LLM + tool allowlist per role, MCP client loop)        │
                  └───────┬───────────────────┬───────────────────┬──────────┘
                          │ MCP               │ MCP               │ MCP (read-only)
                 ┌────────▼───────┐  ┌────────▼────────┐  ┌───────▼─────────────┐
                 │ defi-risk MCP  │  │ defi-memory MCP │  │ @falkordb/mcpserver │
                 │ (ours)         │  │ (ours, per-user)│  │ generic Cypher/schema│
                 └───┬─────────┬──┘  └────────┬────────┘  └───────┬─────────────┘
                     │         │              │                   │
              ┌──────▼──┐  ┌───▼────────┐  ┌──▼───────────┐       │
              │defi_risk│  │defi_evidence│  │ mem_<user>   │◄──────┘ (risk graph only)
              │ (graph) │  │(GraphRAG-SDK)│  │ per user     │
              └─────────┘  └────────────┘  └──────────────┘
                       all in one FalkorDB instance (Docker or FalkorDB Cloud)
```

### 3.3 Repo layout (create exactly this so parallel agents don't collide)

```
bulwark/
  docker-compose.yml          # falkordb (6379, 3000), mcp-falkordb (http, readonly), app
  .env.example                # LLM keys, FALKORDB_HOST/PORT, GRAPH names, BULWARK_GRAPH_OFF
  pyproject.toml
  README.md                   # setup + data model + queries + AI-use disclosure + attribution
  data/
    snapshots/defillama/      # frozen JSON pulls (committed)
    seed/dependencies.yaml    # hand-curated edges, each with source_url + confidence
    seed/incidents.yaml       # ~15 incidents, own-words summaries + source_url
    seed/tags.yaml            # controlled vocabulary + derivation rules
    evidence/*.md             # own-words notes with front-matter: protocol_id, source_url
    scenarios/*.json          # 3 scripted replay scenarios (§12)
  bulwark/
    config.py  db.py          # client factory, graph names, ro/rw helpers
    graph/    schema.py ingest_defillama.py ingest_seed.py derive_tags.py algos.py
    evidence/ ontology.py ingest.py query.py
    risk/     queries.py rules.py engine.py       # ALL Cypher lives in queries.py
    memory/   schema.py store.py reflect.py
    mcp_servers/ risk_server.py memory_server.py
    agents/   runner.py roles.py orchestrator.py
    app/      streamlit_app.py
    sim/      loadtest.py incident_injector.py
  tests/
  docs/       DATA_MODEL.md  QUERIES.md (generated from queries.py)  DEMO_SCRIPT.md
```

### 3.4 Contracts (agree before parallel work starts)

All tool outputs are JSON. These shapes are the interface between workstreams:

```jsonc
// Finding: the unit of explanation. Every verdict is a list of these.
{ "id": "F-<short-hash>",
  "rule": "R1_SHARED_DEPENDENCY",
  "severity": "high|medium|low|info",
  "summary": "Chainlink ETH/USD feed underlies 3 of your 4 positions (62% of capital)",
  "path": ["position:aave-v3", "dep:chainlink-eth-usd", "position:compound-v3"],
  "evidence": [{"kind": "edge", "source_url": "https://...", "confidence": 0.8}],
  "memory_ref": null }               // set when a past Mistake/Rule contributed

// Verdict: the output of assess_proposal.
{ "verdict": "ALLOW|ALLOW_WITH_LIMITS|BLOCK",
  "max_allocation_pct": 12.5,        // present for ALLOW_WITH_LIMITS
  "findings": [ /* Finding */ ],
  "assessed_at": "ISO-8601", "graph_snapshot": "2026-10-17" }

// Position (paper): { "protocol_id": "aave-v3", "chain": "ethereum", "amount_usd": 5000 }
```

---

## 4. Build step 1: the risk graph model

### 4.1 Design principles

1. **Model for the traversals you'll run**, not for the data you have. The core question is "if X breaks, what else breaks?", so there is **one contagion-carrying relationship type, `DEPENDS_ON`**, with a `kind` property. Algorithms accept `nodeLabels`/`relationshipTypes` filters, so we restrict to `DEPENDS_ON` and avoid mixing in non-contagion edges.
2. **Direction = dependency.** `(A)-[:DEPENDS_ON]->(B)` means "A depends on B". A shock at B propagates **backwards** along incoming edges.
3. **Everything claimable has a source.** Hand-curated edges carry `source_url` and `confidence`. No edge from LLM guesswork: a hallucinated dependency is the fastest way to lose credibility.
4. **Tags are derived deterministically** from graph facts, not inferred by an LLM. Tags are the join key to user memory (§4.4).
5. **Index only what you filter on**: `Protocol(id)`, `Chain(id)`, `Asset(id)`, `Oracle(id)`, `Bridge(id)`, `Controller(id)`, `Incident(id)`, `Tag(name)`.

### 4.2 Schema

**Nodes**

| Label | Key properties | Source |
|---|---|---|
| `Protocol` | `id` (DeFiLlama slug), `name`, `category`, `tvl_usd`, `tvl_change_7d`, `age_days`, `audit_count`, `timelock_hours`, `tags[]`, `pagerank`, `betweenness`, `community` | DeFiLlama + seed |
| `Chain` | `id`, `name`, `tvl_usd`, `type` (L1/L2) | DeFiLlama (`/v2/chains`) |
| `Asset` | `id`, `symbol`, `kind` (native/stable/lst/wrapped/lp), `peg_type` (fiat/crypto-backed/algorithmic/n-a), `peg_deviation_pct` | DeFiLlama stablecoins + seed |
| `Pool` | `id`, `protocol_id`, `chain`, `symbols`, `apy`, `tvl_usd` | DeFiLlama pools (only for our protocols) |
| `Oracle` | `id`, `name`, `feed` | seed |
| `Bridge` | `id`, `name`, `mechanism` (native/lock-mint/liquidity/optimistic), plus L2BEAT-style risk fields where known | seed |
| `Controller` | `id`, `type` (multisig/timelock/eoa), `threshold` (e.g. "3/5") | seed |
| `Auditor` | `id`, `name` | seed / DeFiLlama `audits` |
| `Incident` | `id`, `date`, `loss_usd`, `type`, `summary` (own words), `source_url` | seed |
| `Tag` | `name` | `tags.yaml` |

**Relationships**

| Type | Pattern | Properties | Carries contagion? |
|---|---|---|---|
| `DEPENDS_ON` | `Protocol/Pool/Asset -> Oracle/Bridge/Asset/Protocol/Controller` | `kind` (oracle/bridge/collateral/liquidity/stablecoin/controller/underlying), `strength` 0-1, `source_url`, `confidence` | **Yes** |
| `DEPLOYED_ON` | `Protocol -> Chain` | `tvl_usd` | No |
| `AUDITED_BY` | `Protocol -> Auditor` | `date`, `source_url` | No |
| `FORKED_FROM` | `Protocol -> Protocol` | | No |
| `ISSUED_BY` | `Asset -> Protocol` | | No |
| `AFFECTED_BY` | `Protocol/Asset/Bridge -> Incident` | `role` (victim/vector) | No |
| `HAS_TAG` | `Protocol -> Tag` | | No |

`strength` is a **modeling judgment** (how much of the dependent's value rests on the dependency). Set it from a small fixed scale (0.25 / 0.5 / 0.75 / 1.0), document the scale in `DATA_MODEL.md`, and never present derived USD impacts as precise: label them "estimate".

### 4.3 Ingestion (do in this order)

1. **Snapshot DeFiLlama** (`graph/ingest_defillama.py`): pull `/protocols`, `/v2/chains`, `/stablecoins` (+ `/stablecoin/{id}` for chain circulation), `/pools`, and `/protocol/{slug}` for the chosen set. Save raw JSON to `data/snapshots/defillama/` and **commit it**. Load from the snapshot, not the network, by default.
2. **Choose the universe: ~40-60 protocols** across lending, DEX, liquid staking, stablecoin issuers, yield aggregators, bridges, on ~6 chains. Smaller and richer beats bigger and shallow. List the IDs in `data/seed/universe.txt`.
3. **Hand-curate dependencies** (`data/seed/dependencies.yaml`): oracle feeds, bridge-wrapped assets, stablecoin backing, admin controllers, protocol-on-protocol dependencies. **This is the most labor-intensive step. Parallelize across teammates by category**, and start it first. Fallback if short on time: deeply curate the top ~25 and every dependency of those.
4. **Incidents** (`data/seed/incidents.yaml`): ~15 well-documented public incidents (stablecoin depegs, bridge compromises, oracle manipulations, rug pulls). **Write summaries in our own words with a `source_url`**; do not paste post-mortem text. Link with `AFFECTED_BY`.
5. **Derive tags** (`graph/derive_tags.py`) from facts: e.g. `unaudited` (audit_count = 0), `young_protocol` (age_days < 90), `single_oracle`, `wrapped_bridged_asset`, `algorithmic_stablecoin`, `admin_eoa`, `no_timelock`, `tvl_spike`, `high_apy_outlier`, `fork_of_exploited`, `concentrated_one_chain`. Vocabulary lives in `tags.yaml`. Thresholds are illustrative policy; tune and document them.
6. **Precompute algorithms** (`graph/algos.py`) on the dependency subgraph and store results as node properties: PageRank (systemic importance), betweenness (choke points), WCC/CDLP (hidden clusters of protocols that share infrastructure). Details in §6.2. Rerun after any data change.
7. **Verify in FalkorDB Browser** (`localhost:3000`): node/edge counts, no orphan `Protocol` nodes, every `DEPENDS_ON` has `source_url`.

**Acceptance (tests):** counts match the seed files; every `DEPENDS_ON` has a non-empty `source_url`; every `Protocol.tags` value exists in the vocabulary; reload is idempotent (use `MERGE`).

---

## 5. Build step 2: the evidence layer (GraphRAG-SDK)

### 5.1 Do we need it? Yes, for one job.

| Data | Right tool |
|---|---|
| Structured market/dependency data (TVL, chains, edges) | Direct Cypher loads (§4). The SDK adds LLM cost and noise here |
| **Unstructured evidence**: audit-finding summaries, incident post-mortems, governance/risk docs | **GraphRAG-SDK**: ontology-constrained extraction, vector + full-text + relationship-expansion retrieval, provenance edges (`MENTIONED_IN`) from entity to source chunk, `return_context=True`, and abstention |

This earns its place because risk claims must be **cited** and the agent must **abstain** ("no audit evidence in our graph") instead of guessing. Absence of evidence is surfaced as a finding, never silently treated as "safe".

**Cut-line fallback:** if ingestion cost/time becomes a problem, replace with hand-written `Evidence` nodes (`text`, `source_url`) linked to protocols in `defi_risk`. We'd lose the GraphRAG story but keep everything else. The hackathon lists the SDK as an integration, not a requirement.

### 5.2 Usage (from the SDK README; confirm against installed version)

```bash
pip install "graphrag-sdk[litellm]"          # add ,pdf if ingesting PDFs
# FalkorDB already running: docker run -d -p 6379:6379 -p 3000:3000 falkordb/falkordb:latest
```

```python
from graphrag_sdk import (GraphRAG, ConnectionConfig, LiteLLM, LiteLLMEmbedder,
                          GraphSchema, EntityType, RelationType)

schema = GraphSchema(
    entities=[
        EntityType(label="Protocol",  description="A DeFi protocol or application"),
        EntityType(label="Incident",  description="An exploit, depeg, or failure event"),
        EntityType(label="Finding",   description="An audit finding or identified weakness"),
        EntityType(label="Component", description="Oracle, bridge, contract, or admin mechanism"),
    ],
    relations=[
        RelationType(label="HAS_FINDING",  description="Protocol has this audit finding", patterns=[("Protocol","Finding")]),
        RelationType(label="SUFFERED",     description="Protocol suffered this incident", patterns=[("Protocol","Incident")]),
        RelationType(label="EXPLOITED_VIA",description="Incident exploited this component", patterns=[("Incident","Component")]),
    ],
)

async with GraphRAG(
    connection=ConnectionConfig(host="localhost", graph_name="defi_evidence"),
    llm=LiteLLM(model=ENV_LLM_MODEL),                         # model string from env
    embedder=LiteLLMEmbedder(model=ENV_EMBED_MODEL, dimensions=256),
    schema=schema,
) as rag:
    await rag.ingest(text=note_text, document_id=f"{protocol_id}:{note_slug}")
    await rag.finalize()                                      # once per batch (dedupe is O(graph))
    ans = await rag.completion(question, return_context=True)
```

- Batch-ingest all notes, call `finalize()` **once**.
- Read the SDK's `grounded_answers_with_abstention.py` example and wrap it in `evidence/query.py`: `get_evidence(protocol_id, question)` returns `{answer, citations[], status: "GROUNDED"|"ABSTAIN"}`. On `ABSTAIN`, the risk engine emits an `info`/`medium` finding "no evidence on file".
- Re-sync changed notes with `update` / `delete_document` / `apply_changes` instead of rebuilding.
- **Keep ingestion bounded** (~20-30 short notes). Extraction is LLM-priced; **start the ingestion job early and let it run in the background.**
- Text-to-Cypher retrieval is marked experimental in the SDK. Treat it as optional.
- Notes are **our own-words summaries** with `source_url` in front-matter. Don't ingest copyrighted post-mortem or audit text verbatim.

---

## 6. Build step 3: the risk engine (how risk is assessed and managed)

### 6.1 Principle: structure + evidence + person, combined deterministically

Risk is **not** one score. It's a set of **findings**, each tied to a graph path, a source, or a memory, rolled into a verdict by explicit rules.

### 6.2 The three layers

**Layer A: Structural risk (multi-hop traversals + graph algorithms)**

- *Shared-dependency exposure*: for the user's positions (+ the proposed one), find dependency nodes (oracle/bridge/controller/asset) within ≤3 hops shared by ≥2 positions. Output concentration: "X underlies 3 of 4 positions = 62% of capital".
- *Shock simulation*: pick a failure node (a stablecoin depeg, a bridge compromise, an oracle failure) and walk **incoming** `DEPENDS_ON` edges ≤4 hops to list affected protocols with hop counts and a strength-weighted impact estimate.
- *Systemic importance*: PageRank and betweenness centrality over `DEPENDS_ON` identify choke points. Precompute and store as node properties; also expose one **live** algorithm call as a tool so the demo shows an algorithm used as a tool.
- *Hidden clusters*: WCC/CDLP finds protocols that look independent but share infrastructure. Use to power diversification ("not connected" proofs).
- *Diversifiers*: find same-category alternatives with **no** shared dependency with the current portfolio. This "proving the absence of links" query is a pattern the August FalkorDB hackathon highlighted.

Algorithms are called with `CALL algo.<name>(...)`. Names available per the docs: `BFS`, `SPpaths`, `SSpaths`, `MSF`, `pageRank`, betweenness, harmonic centrality, `WCC`, `CDLP`, `MaxFlow`. **Read each algorithm's page before coding it; do not guess signatures**: `https://docs.falkordb.com/algorithms` (individual pages under `/algorithms/<name>`). Most accept `nodeLabels` / `relationshipTypes`.

**Layer B: Evidential risk**: `get_evidence` (§5). Findings carry citations; no evidence = explicit "unverified" finding.

**Layer C: Personal risk**: memory joins (§8): user preference limits, matched past mistakes, and learned rules.

### 6.3 Rule engine (`risk/rules.py`)

Thresholds are **illustrative policy**: expose as config, document them, tune on the demo scenarios.

| Rule | Fires when | Severity | Effect |
|---|---|---|---|
| R1 Shared dependency | a single dependency node underlies >40% of post-trade capital | high | cap allocation |
| R2 Immature/unaudited | `age_days < 90` or `audit_count = 0` | medium | cap allocation (e.g. 5%) |
| R3 Risky provenance | asset reached via a bridge with a recorded incident | high | block or cap |
| R4 Stablecoin integrity | algorithmic peg, or `peg_deviation_pct` > 1 | high | block |
| R5 Admin risk | controller is `eoa`, or multisig threshold < 3 with no timelock | medium/high | cap |
| R6 Liquidity/TVL shock | `tvl_change_7d` < -30% | medium | warn |
| R7 Past mistake match | user has a `Mistake` whose tags overlap the proposal's tags | medium/high | per learned `Rule.action` |
| R8 Preference violation | proposal exceeds the user's stated limits or avoided chains | high | block or cap |
| R9 No evidence | `get_evidence` abstained | low | warn ("unverified", not "safe") |

Verdict logic: any `block` action → **BLOCK**; else any `cap` → **ALLOW_WITH_LIMITS** with `max_allocation_pct = min(caps)`; else **ALLOW**. Every finding includes its `path` and `evidence`.

### 6.4 How risk is *managed* (after assessment)

1. **Position limits** from the verdict (`ALLOW_WITH_LIMITS`).
2. **Alternatives**: `find_diversifiers` proposes lower-overlap options.
3. **Gate**: `open_position` (paper) is refused by the server unless a fresh verdict ≠ BLOCK exists for that exact proposal (D7).
4. **Monitoring** (stretch/demo highlight): `sim/incident_injector.py` writes a new `Incident` + status change into `defi_risk`, then re-evaluates every user's exposure (iterate user graphs) and writes an `Alert` node per affected user. Doubles as the concurrency demo.

**Acceptance:** unit tests on a tiny FalkorDBLite fixture graph with known answers for each rule and for exposure/shock queries.

---

## 7. Build step 4: MCP servers and LLM tool use

### 7.1 Three MCP servers (so the agent has a real tool-selection decision)

1. **`defi-risk`** (ours, Python, MCP SDK `FastMCP`): read-only domain tools on `defi_risk` + `defi_evidence`.
2. **`defi-memory`** (ours, Python): read/write tools on the caller's `mem_<user>` graph. **One stdio subprocess per session with `BULWARK_USER_ID` set** (D5).
3. **`@falkordb/mcpserver`** (official, run with `FALKORDB_DEFAULT_READONLY=true`, pointed at the risk graph): generic `query_graph_readonly`, `list_graphs`, `get_graph_schema`, `get_node_schema`, `get_relationship_schema`. This is the escape hatch for ad-hoc questions our curated tools don't cover.

### 7.2 Tool catalog

**`defi-risk` (read-only)**

| Tool | Purpose |
|---|---|
| `find_protocols(category?, chain?, min_tvl?, exclude_tags?, limit)` | candidate discovery |
| `get_protocol_profile(protocol_id)` | facts, tags, 1-hop dependencies, audits, incidents |
| `get_dependency_paths(protocol_id, max_hops=3)` | multi-hop dependency tree with sources |
| `portfolio_exposure(positions[])` | shared dependencies and concentration |
| `simulate_shock(node_id)` | contagion paths + affected positions + estimated impact |
| `systemic_importance(node_id)` | PageRank / betweenness / community + one live algorithm call |
| `find_diversifiers(category, positions[])` | same-category alternatives with no shared dependency |
| `get_evidence(protocol_id, question)` | GraphRAG-SDK answer + citations, or `ABSTAIN` |
| `assess_proposal(proposal, user_prefs, user_rules)` | the rule engine → `Verdict` |

`assess_proposal` takes the user's preferences/rules **as arguments supplied by the orchestrator** (read from the memory server), keeping the risk server tenant-agnostic and stateless.

**`defi-memory` (per-user; `user_id` bound server-side)**

| Tool | Purpose |
|---|---|
| `memory_brief()` | top preferences + active rules + recent episodes + open tasks, for session start |
| `get_portfolio()` | current paper positions |
| `remember_preference(key, value, source)` | semantic memory write |
| `recall_relevant_mistakes(protocol_tags[])` | overlap lookup (the memory→risk join) |
| `record_outcome(position_id, outcome, loss_usd?, notes)` | creates `Episode`, a `Mistake` if regret/loss, and a *candidate* `Rule` |
| `confirm_rule(rule_id, accept)` | human-in-the-loop for procedural memory |
| `open_position(proposal_id)` / `close_position(position_id)` | paper execution; **enforces the gate** |
| `get_task_board()` | handoff state for the UI trace |

### 7.3 How the LLM calls MCP tools (agent loop; `agents/runner.py`)

```python
# Pseudocode. Package/class names from the official MCP Python SDK; verify against installed version.
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def run_agent(role, user_msg, servers, llm, max_steps=8):
    async with AsyncExitStack() as stack:
        sessions = {name: await stack.enter_async_context(connect(name, params)) for name, params in servers}
        tools = []                                    # merge tool lists, namespace as "<server>__<tool>"
        for name, s in sessions.items():
            for t in (await s.list_tools()).tools:
                if f"{name}__{t.name}" in ROLE_ALLOWLIST[role]:
                    tools.append(to_llm_tool_schema(name, t))
        messages = [system(role), *history, user(user_msg)]
        for _ in range(max_steps):
            resp = await llm.chat(messages, tools=tools)
            if not resp.tool_calls:
                return resp.text
            for call in resp.tool_calls:
                server, tool = call.name.split("__", 1)
                result = await sessions[server].call_tool(tool, call.arguments)
                trace.append({"role": role, "tool": call.name, "args": call.arguments, "result": summarize(result)})
                messages.append(tool_result(call.id, truncate(result)))
        raise StepLimit()
```

Guardrails: `max_steps`, per-role **tool allowlists**, truncate large results, log every call to the `trace` (shown in the UI and stored as `Turn` nodes), and a timeout per tool.

### 7.4 Explainability enforcement

The final answer is requested as JSON: `{verdict, reasons:[{finding_id, text}], next_steps}`. A validator rejects any `finding_id` not returned by a tool in this run (one retry, then fall back to a templated summary of the findings). This is what makes "explainable results" a property of the system, not a prompt hope.

The agent also works as a plain MCP server in **Claude Desktop / Cursor**: point the client config at `defi-risk` and `defi-memory`. That makes a nice 20-second bonus clip: the same graph serving a stock MCP client.

---

## 8. Build step 5: the memory layer (personalization, past errors, where it lives)

### 8.1 Where it lives

One graph per user: **`mem_<user_id>`**. Everything about that person (preferences, episodes, mistakes, learned rules, paper positions, chat history, tasks) lives only there. Separate memory per user, isolated by construction, deletable by dropping the graph.

### 8.2 Memory types mapped to the track's key-focus bullets

| Type | Graph model | Example | Written by |
|---|---|---|---|
| **Semantic** (facts/preferences) | `(:User)-[:HAS_PREFERENCE]->(:Preference {key, value, strength, updated_at})` | max 20% per protocol; avoid chain Y; moderate risk tolerance | `remember_preference`, onboarding, chat |
| **Episodic** (what happened) | `(:Episode {id, ts, kind, summary, outcome})-[:INVOLVED]->(:ProtocolRef {protocol_id})`, `(:Episode)-[:HAD_TAG]->(:Tag)` | "Opened 15% in a young, unaudited fork; lost 40% in replay scenario B" | `record_outcome`, session end |
| **Mistakes** (past errors) | `(:Mistake {id, ts, description, loss_usd, root_cause})-[:FROM_EPISODE]->(:Episode)`, `(:Mistake)-[:CAUSED_BY_TAG]->(:Tag)` | tags: `unaudited`, `young_protocol` | `record_outcome` (or typed in at onboarding, §8.4) |
| **Procedural** (learned rules) | `(:Rule {id, text, trigger_tags[], action: warn/cap/block, cap_pct?, confidence, times_triggered, times_overridden, status: proposed/active})-[:DERIVED_FROM]->(:Mistake)` | "After a loss on unaudited forks: cap such protocols at 5% and require an audit" | `reflect.py` proposes → user confirms |
| **Portfolio** (paper) | `(:Position {id, protocol_id, chain, amount_usd, opened_at, status})` | | `open_position` / `close_position` |
| **Conversation history** | `(:Session)-[:HAS_TURN]->(:Turn {role, text, ts, tool_trace?})`, plus a per-session `summary` | persists across restarts | runner |
| **Shared state / handoffs** | `(:Task {id, status, owner, proposal})-[:PRODUCED]->(:Finding)`, `(:Task)-[:HANDOFF {from, to, ts}]->(:Task)` | analyst→guardian→executor | orchestrator (§9) |

### 8.3 How memory changes decisions (the join)

The risk graph tags each protocol (`Protocol.tags`). The user graph tags each `Mistake`. The tool `recall_relevant_mistakes(protocol_tags)` finds `Mistake`/`Rule` nodes whose tags overlap. The orchestrator passes them into `assess_proposal`, so rule **R7** fires with `memory_ref` pointing at the originating episode. Two reads, no cross-graph query (D4).

Controlled tag vocabulary is essential: `Mistake` tags are LLM-*proposed* but **validated against `tags.yaml`**; anything outside the vocabulary is dropped.

### 8.4 Creating the memory

1. **Onboarding**: 4-5 questions (risk tolerance, max per protocol, avoided chains, horizon). Write `Preference` nodes. Optional free-text "tell me about a past DeFi loss": an LLM extracts a structured `Mistake` with vocabulary-validated tags.
2. **During chat**: the agent calls `remember_preference` when the user states a constraint ("never more than 10% in anything new"). Show a visible "memory updated" chip in the UI.
3. **After an outcome** (replay scenario or manual): `record_outcome` writes the `Episode`; if there was a loss/regret, writes a `Mistake`; `reflect.py` has the LLM propose a `Rule` (status `proposed`). The UI asks **"I learned this rule from your loss: keep it?"** → `confirm_rule`. Human-in-the-loop keeps memory trustworthy and makes the demo moment legible.
4. **Session start**: `memory_brief()` is injected into the system prompt (top preferences, active rules, last episodes, open tasks) and the last N turns/summary are loaded.
5. **Session end**: summarize the session into an `Episode` + `Session.summary`.

### 8.5 Persistence and concurrency (Track 2 bullets)

- **Persistence must survive a restart.** FalkorDB persistence depends on volume mounts and Redis persistence flags. The official MCP server's compose file notes a volume path pitfall (volume mounted at `/data` while the image writes to `/var/lib/falkordb/data`). **Test early**: write memory → `docker restart falkordb` → read memory. Fix the mount if it fails. The cross-session demo depends on this.
- **High-concurrency reads/writes**: use the async client (`falkordb.asyncio`) with a connection pool. `sim/loadtest.py` simulates N users (start at 100) each with its own graph doing mixed `memory_brief` reads and `record_outcome` writes **concurrently**, and reports p50/p95 latency and throughput. **Report only numbers we measure.** Whether writes within one graph are serialized is a property to *verify*, which per-user graphs sidestep.

---

## 9. Build step 6: agents and handoffs

**Pattern: graph-as-blackboard with a deterministic orchestrator.** Three LLM roles with different prompts and tool allowlists, coordinated by a small state machine reading/writing `Task` nodes in the user's graph.

| Role | Allowed tools | Job | Writes |
|---|---|---|---|
| **Analyst** | all `defi-risk` read tools + generic FalkorDB MCP (read-only) + `memory_brief`, `recall_relevant_mistakes` | gather facts, run exposure/shock/diversifier tools, produce a proposal + findings | `Task(status=analyzed)` + `Finding` nodes |
| **Guardian** | `assess_proposal`, `recall_relevant_mistakes`, `get_task_board` | independently re-run the rule engine, check personal rules, approve / cap / veto | `Task(status=approved|blocked)` |
| **Executor** | `open_position`, `close_position`, `get_portfolio` | paper-execute **only** approved tasks | `Task(status=executed)` + `Episode` |

Flow: `proposed → analyzed → approved|blocked → executed`. Each transition is a `HANDOFF` edge with from/to/timestamp. Handoffs are visible in FalkorDB Browser and the UI task board. Even if an LLM-based Executor goes rogue, the **server-side gate** (D7) still refuses.

**Cut-line:** if time is short, collapse to one agent with role-prompted phases. Keep the `Task` nodes and the server-side gate either way.

---

## 10. Build step 7: app and UI

- **Streamlit** app: chat; **tool-call trace** panel (role, tool, args, summarized result); **explanation graph** panel rendering the finding `path`s (pyvis or similar); task board; "memory updated" and "learned rule: keep?" chips; user switcher (alice/bob) to demonstrate isolation; "not financial advice, paper trading only" banner.
- **FalkorDB Browser** (`localhost:3000`) is the "real graph" tab in the demo.
- **Fallback** if the UI slips: CLI (Rich) + FalkorDB Browser. The graph and memory are the product, not the front-end.
- **Deployment:** `docker compose up` (falkordb + MCP + app). Optional live deploy against a FalkorDB Cloud free instance. If we can't deploy, the README must have complete local setup plus the demo video.

---

## 11. Workstreams for parallel agents

Contracts in §3.4 and the repo layout in §3.3 let these run in parallel with minimal collisions:

| WS | Scope | Depends on | Done when |
|---|---|---|---|
| **A. Data/graph** | §4 ingestion, tags, algos | contracts | graph loaded; acceptance tests pass; Browser check |
| **A2. Curation** (human-heavy) | `dependencies.yaml`, `incidents.yaml`, `evidence/*.md` | universe list | ≥25 protocols fully curated, sources on every edge |
| **B. Risk engine + risk MCP** | §6, §7 `defi-risk` | schema from A | rule tests pass on fixture graph; tools return contract JSON |
| **C. Evidence** | §5 | notes from A2 | `get_evidence` returns GROUNDED/ABSTAIN with citations |
| **D. Memory + memory MCP** | §8, `defi-memory` | contracts | persistence-after-restart test passes; per-user isolation test passes |
| **E. Agents + UI** | §7.3, §9, §10 | B, D tool schemas (use mocks until ready) | end-to-end happy path |
| **F. Demo/sim** | §12 scenarios, load test, incident injector, graph-off switch | B, D | scripted demo runs start to finish |

---

## 12. How to demo each objective (video + live)

### 12.1 Scenarios (`data/scenarios/*.json`)

Three scripted **replay** scenarios against a paper portfolio, inspired by well-known incident *types*: **(A)** stablecoin depeg, **(B)** bridge compromise collapsing a wrapped asset, **(C)** oracle manipulation on a lending market. Source facts from public post-mortems and write them in our own words with URLs. A scenario applies a shock to the paper portfolio so there's a concrete "loss" to remember, without waiting for reality.

### 12.2 Demo beats (target ≤4 minutes; each maps to a key-focus bullet)

| # | Beat | What the judge sees | Key-focus bullet |
|---|---|---|---|
| 1 | "Put 30% into protocol X" | Analyst runs `get_protocol_profile` → `portfolio_exposure` → `simulate_shock`; UI draws the **path** to a shared oracle; verdict with cited findings | T1 multi-hop reasoning; explainable results |
| 2 | "Which other protocols share that oracle?" | Agent picks the **generic FalkorDB MCP** (not a curated tool), runs a read-only Cypher, shows the trace | T1 tool selection through MCP |
| 3 | "How systemic is this oracle?" | `systemic_importance`: live algorithm call + precomputed PageRank/community | T1 graph algorithms as tools |
| 4 | Executor tries to open the blocked position | **Server refuses**, citing the finding id; then a capped version succeeds | T1 actions based on what the graph shows |
| 5 | **Memory, session 1:** alice states preferences → replay scenario → loss recorded → "I learned this rule: keep?" → accept | `Preference`, `Episode`, `Mistake`, `Rule` appear in `mem_alice` in Browser | T2 episodic / semantic / procedural |
| 6 | **Memory, session 2:** kill the app **and** `docker restart falkordb`; start a fresh chat as alice | Agent opens with the `memory_brief`; proposing a similar young/unaudited protocol triggers **R7** citing the earlier episode | T2 persistent history; memory changes decisions |
| 7 | **Isolation:** switch to bob, ask the same question | Different answer, empty memory; two memory graphs side by side in Browser | T2 separate memory per user |
| 8 | **Handoffs:** show the task board | Analyst → Guardian → Executor as `HANDOFF` edges in the graph | T2 shared state and handoffs |
| 9 | **Concurrency + incident injection:** run `loadtest` with 100+ users, inject an incident, show per-user alerts | measured p50/p95 and throughput on screen | T2 high-concurrency reads/writes |
| 10 | **Graph-off test:** run with `BULWARK_GRAPH_OFF=1` | tools return empty; agent can't produce path-based verdicts and abstains or goes generic | rule 3: the graph is the product |

**Also record:** a 20-second clip of Claude Desktop/Cursor using our MCP servers (stock MCP client = interoperability).

### 12.3 Numbers to capture for the README and video

Node/edge counts per graph; tool latency p50/p95; load-test users and throughput; number of curated edges with sources; number of evidence documents ingested. **No figure goes in the README unless we measured it.**

---

## 13. Timeline (IST) and cut lines

| Window | Goal |
|---|---|
| **Sat 16:30-19:00** | Repo + compose up; contracts agreed; DeFiLlama snapshot committed; universe chosen; **curation starts**; memory schema; **persistence-after-restart test** |
| **Sat 19:00-24:00** | Graph loaded + tags + algos; risk queries + rule engine on fixtures; `defi-risk` MCP v1; **start evidence ingestion in background** |
| **Sun 00:00-08:00** | Sleep/buffer for humans. Agents can run long jobs (evidence ingestion, load-test harness, tests) |
| **Sun 08:00-14:00** | `defi-memory` MCP + reflection; agents + orchestrator; Streamlit UI; scenarios |
| **Sun 14:00-18:00** | Integration; incident injector; load test; graph-off switch; bug bash. **Feature freeze at 18:00** |
| **Sun 18:00-21:30** | Record video; README (setup, data model, queries, AI disclosure, attribution); generate `docs/QUERIES.md`; blog post (side prize); **submit by ~21:30**, leaving a 2h+ buffer |

**Cut order if behind (cut from the top):**
1. Incident-injection fan-out across users.
2. Multi-agent → single agent with role-prompted phases (keep `Task` nodes + server-side gate).
3. GraphRAG-SDK evidence → hand-written `Evidence` nodes.
4. Streamlit polish → CLI + FalkorDB Browser.

**Never cut:** risk graph with sourced edges, the rule engine, per-user memory graphs, the server-side action gate, the cross-session memory demo, the graph-off test.

---

## 14. Submission checklist

- [ ] Public repo; README has setup, **graph data model**, AI-use disclosure, DeFiLlama attribution
- [ ] `docs/QUERIES.md`: the Cypher queries and algorithms the product depends on (generate from `risk/queries.py`)
- [ ] Demo video showing beats 1-10
- [ ] Live deployment, or complete local setup instructions (`docker compose up`) plus the video
- [ ] Tracks named at submission: **Agents That Act on Connected Data** and **Agent Memory and Coordination**
- [ ] Only public/synthetic/own data; no private data, no real funds/keys
- [ ] Every teammate can explain the graph model, queries, and architecture
- [ ] Blog post (AirPods side prize)

---

## 15. Cypher skeletons (UNTESTED; verify in FalkorDB Browser first)

FalkorDB gotchas from the docs: parameters are **not allowed in `LIMIT`/`SKIP`**; if a relationship alias isn't referenced elsewhere in a query, only existence is checked, so counts can be off; `LIMIT` doesn't stop eager writes; aggregations aren't allowed inside pattern comprehensions; `<>` filters don't use indexes. Use the official read-only query call (`ro_query`/`GRAPH.RO_QUERY`) for all reads on `defi_risk`.

```cypher
// Shared dependencies across a set of positions (portfolio_exposure)
UNWIND $positions AS pos
MATCH (p:Protocol {id: pos.protocol_id})-[d:DEPENDS_ON*1..3]->(dep)
WHERE dep:Oracle OR dep:Bridge OR dep:Controller OR dep:Asset
WITH dep, collect(DISTINCT p.id) AS protocols
WHERE size(protocols) >= 2
RETURN dep.id AS dependency, labels(dep)[0] AS type, protocols
ORDER BY size(protocols) DESC

// Shock simulation: who breaks if node $shock_id fails? (walk incoming edges)
MATCH path = (shock {id: $shock_id})<-[:DEPENDS_ON*1..4]-(p:Protocol)
RETURN p.id AS affected, length(path) AS hops, [n IN nodes(path) | n.id] AS chain
ORDER BY hops

// Protocols sharing an oracle with $protocol_id (also a good generic-MCP demo query)
MATCH (a:Protocol {id: $protocol_id})-[:DEPENDS_ON]->(o:Oracle)<-[:DEPENDS_ON]-(b:Protocol)
WHERE b.id <> a.id
RETURN o.id AS oracle, collect(DISTINCT b.id) AS also_depends

// Diversifiers: same category, no dependency shared with current portfolio
MATCH (c:Protocol {category: $category})
WHERE NOT c.id IN $held_ids
  AND NOT EXISTS {
    MATCH (c)-[:DEPENDS_ON*1..3]->(dep)<-[:DEPENDS_ON*1..3]-(h:Protocol)
    WHERE h.id IN $held_ids
  }
RETURN c.id, c.name, c.tvl_usd, c.tags
ORDER BY c.tvl_usd DESC
LIMIT 10
```

If `EXISTS { ... }` subqueries aren't supported in the installed version, compute shared-dependency sets per candidate in the app layer instead.

---

## 16. Known unknowns (verify before relying on them)

1. DeFiLlama endpoint hosts and response shapes; whether any hacks/oracle/bridge datasets are available free (we assume **no**, hence hand-curation).
2. Exact signatures for `algo.*` procedures. Read each docs page.
3. That cross-graph Cypher is unsupported (assumed in D4).
4. GraphRAG-SDK API details beyond the README (v1.x); ingestion time/cost; text-to-Cypher is experimental.
5. MCP Python SDK class/function names in the pseudocode (§7.3).
6. Docker persistence after restart (§8.5).
7. DeFiLlama attribution/terms.
8. All thresholds in §6.3 are our own illustrative policy, not industry standards. Say so in the README.
