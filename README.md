# Bulwark — FalkorDB Graph Setup & Data Ingestion

This repository sets up Bulwark's graph database using FalkorDB. It ingests DeFi protocol, chain, stablecoin, pool, and incident data from DeFiLlama, then adds curated oracle relationships and evidence provenance.

## 1. Prerequisites

- Python 3.10+
- Docker and Docker Compose, or a running FalkorDB instance
- Internet access for fetching DeFiLlama API data

## 2. Setup

Clone the repository and navigate to its root directory (`graphino`).

```bash
git clone <repository-url>
cd graphino
```

Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start FalkorDB if it is not already running. If your repository includes a Docker Compose configuration, use:

```bash
docker compose up -d
```

Configure the connection using `.env.example` as a reference. Set the FalkorDB host and port as required by your environment.

## 3. Run the scripts in order

Run the following commands from the repository root.

### Step 1: Initialize the graphs

```bash
python -m scripts.init_graphs
```

Initializes the graph namespaces and creates their metadata.

### Step 2: Ingest DeFiLlama data

```bash
python -m scripts.ingest_defillama
```

Fetches and stores API snapshots, selects relevant protocols and chains, ingests stablecoin assets and liquidity pools, and adds available structured incident records.

The raw API snapshots are saved under `data/raw/`, with processed chain selections under `data/processed/`.

### Step 3: Seed curated relationships and evidence

```bash
python -m scripts.seed_curated_relationships
```

Adds the curated oracle nodes, oracle associations, and documentation evidence used by the current implementation.

**Note:** Oracle associations must not automatically be treated as risk dependencies. The risk engine should explicitly exclude unverified or `risk_eligible = false` relationships.

### Step 4: Verify the graph

```bash
python -m scripts.check_ingestion
```

Reports node counts by label, relationship counts by type, and sample protocols, incidents, and pools.

### Step 5: Inspect FalkorDB

Open FalkorDB Browser at `http://localhost:3000` if it is available in your setup. Select `defi_risk` to inspect the shared risk graph and `defi_evidence` to inspect evidence records.

The per-user memory graphs are separate namespaces and are initialized independently.

## 4. Graph namespaces

| Graph | Purpose |
|---|---|
| `defi_risk` | Shared DeFi entities, relationships, and risk-propagation data |
| `defi_evidence` | Evidence records, documentation URLs, and source provenance |
| `mem_<user_id>` | Isolated per-user preferences, past episodes, learned rules, and other memory records |

## 5. Data provenance

The table below documents the current ingestion and seeding approach. DeFiLlama-derived fields are sourced from the relevant API responses; curated records are explicitly identified as seeded.

| Graph | Attribute | Where it is taken from or seeded |
|---|---|---|
| `defi_risk` | `GraphMeta` | Seeded by `scripts/init_graphs.py` |
| `defi_risk` | Protocol name, ID, slug, URL, description, category, TVL, chains | DeFiLlama `/protocols` API |
| `defi_risk` | Protocol detail fields, including structured `hacks` records where available | DeFiLlama `/protocol/{slug}` API |
| `defi_risk` | Chain name, chain ID, TVL, token symbol | DeFiLlama `/v2/chains` API |
| `defi_risk` | Stablecoin assets and metadata | DeFiLlama `/stablecoins` API |
| `defi_risk` | Pool project, symbol, TVL, APY, underlying tokens, and related pool metrics | DeFiLlama `/pools` API from `yields.llama.fi` |
| `defi_risk` | `DEPLOYED_ON` | Derived from the protocol's reported chain list |
| `defi_risk` | `HAS_POOL` | Seeded from the association between a selected protocol and its ingested pools |
| `defi_risk` | `ON_CHAIN` | Seeded from the pool/chain association during ingestion |
| `defi_risk` | `RELATED_TO` | Derived from DeFiLlama `otherProtocols`; not treated as a verified dependency |
| `defi_risk` | `AFFECTED_BY` | Derived from available structured incident records during ingestion |
| `defi_risk` | `Incident` nodes | Seeded from structured incident information returned by protocol details |
| `defi_risk` | `Oracle` nodes | Curated and seeded by `scripts/seed_curated_relationships.py` |
| `defi_risk` | `USES_ORACLE` | Curated and seeded by `scripts/seed_curated_relationships.py`; verification and risk eligibility are tracked separately |
| `defi_risk` | `Controller` node and `GOVERNED_BY` | May exist from earlier seed/test scripts; verify their source and provenance before relying on them |
| `defi_risk` | `DEPENDS_ON` | May contain test edges from `test_graph.py` and/or curated edges. Verify their provenance and eligibility before using them in risk propagation |
| `defi_risk` | `ASSOCIATED_WITH_ASSET` | Candidate association derived or seeded from available token/stablecoin metadata; not automatically a verified dependency |
| `defi_evidence` | `GraphMeta` | Seeded by `scripts/init_graphs.py` |
| `defi_evidence` | `Evidence` ID, title, URL, source type | Seeded by `scripts/seed_curated_relationships.py` from the curated documentation records |
| `mem_<user_id>` | `GraphMeta` | Seeded by `scripts/init_graphs.py` |
| `mem_<user_id>` | Preferences, episodes, mistakes, rules, sessions, and tasks | Intended to be created by the memory subsystem as users interact with Bulwark; not populated by DeFiLlama ingestion |

## 6. Important relationship semantics

- `DEPENDS_ON` represents a verified dependency only when its source and scope have been validated.
- `RELATED_TO` represents an association and must not be substituted for `DEPENDS_ON`.
- `USES_ORACLE` records an oracle association. It does not automatically imply that the relationship is eligible for risk propagation.
- Test-created relationships should be identified and excluded from production risk calculations until verified.
- Evidence records live in a separate graph. Link them to risk entities through stable IDs or slugs in application code; do not assume cross-graph Cypher joins are available.

## 7. Current scope and next steps

The current ingestion covers a selected subset of DeFiLlama data rather than the entire DeFi ecosystem. Oracle, bridge, controller, auditor, and dependency relationships require additional curated, source-backed coverage.

Next, implement and test bounded risk propagation over eligible dependency edges, using synthetic incidents before integrating risk verdicts into the application.

## 8. Data attribution

Protocol, chain, stablecoin, pool, and available incident information is sourced from the public DeFiLlama APIs. Curated relationships should retain their official documentation URLs, and test data should be clearly identified. This project uses the data for research and demonstration; graph associations alone do not establish that a protocol is safe or unsafe.