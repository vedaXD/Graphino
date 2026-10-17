# Bulwark / Graphino — FalkorDB graph bootstrap

This starter initializes the first graph structure for Bulwark.

## Graphs

- `defi_risk`: shared DeFi protocol, chain, asset, pool, oracle, bridge, controller, auditor, incident, and tag graph.
- `defi_evidence`: evidence documents and findings with source provenance.
- `mem_alice`, `mem_bob`: separate demo memory graphs. In the app, derive memory graph names from the authenticated server-side user ID; never let the LLM choose a tenant.

FalkorDB is schema-flexible. The labels and relationship types are documented in `src/graph_schema.py`; they become actual graph elements as nodes/edges are written. The bootstrap creates `GraphMeta` and indexes.

## Setup

From the `graphino` project root:

```bash
python -m venv .venv
# Windows PowerShell:
.venv\\Scripts\\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` if your Docker container exposes a different host port or requires credentials.

If Docker maps host port `6379` to container port `6379`, use `localhost:6379`. Check with `docker ps`.

## Initialize

```bash
python -m scripts.init_graphs
python -m scripts.inspect_graphs
```

If Python cannot import `src`, run both commands from the `graphino` root. You can add an empty `scripts/__init__.py` if your environment expects it.

## Core risk graph model

Node labels:
`Protocol`, `Chain`, `Asset`, `Pool`, `Oracle`, `Bridge`, `Controller`, `Auditor`, `Incident`, `Tag`.

Relationship types:
- `(:Protocol)-[:DEPENDS_ON {kind, strength, source_url, confidence}]->(:Protocol|Chain|Asset|Oracle|Bridge)`
- `(:Protocol)-[:DEPLOYED_ON]->(:Chain)`
- `(:Protocol)-[:USES_ASSET]->(:Asset)`
- `(:Protocol)-[:ISSUES_ASSET]->(:Asset)`
- `(:Protocol)-[:HAS_POOL]->(:Pool)`
- `(:Protocol)-[:USES_ORACLE]->(:Oracle)`
- `(:Protocol)-[:ROUTES_THROUGH]->(:Bridge)`
- `(:Protocol)-[:CONTROLLED_BY]->(:Controller)`
- `(:Protocol)-[:AUDITED_BY]->(:Auditor)`
- `(:Protocol)-[:AFFECTED_BY]->(:Incident)`
- `(:Protocol)-[:HAS_TAG]->(:Tag)`
- `(:Protocol)-[:FORKED_FROM]->(:Protocol)`

**Direction convention:** for `DEPENDS_ON`, `A -> B` means “A depends on B.” A shock to B can therefore be propagated to dependents by traversing incoming `DEPENDS_ON` edges. Do not create this edge from `otherProtocols` alone.

## Evidence graph model

- `(:Evidence)-[:ABOUT_PROTOCOL]->(:ProtocolRef)` is intentionally not a cross-graph edge. FalkorDB graphs are separate namespaces, so use a `protocol_id`/slug string and join in application code.
- Within `defi_evidence`, keep evidence nodes self-contained with `protocol_id`, `incident_id`, `source_url`, and provenance fields. Use `ABOUT_PROTOCOL` / `DOCUMENTS_INCIDENT` only if you also create local reference nodes or evidence-local IDs.

## Memory graph model

Use separate graph namespaces per authenticated user. Suggested patterns:
- `(:User)-[:HAS_PREFERENCE]->(:Preference)`
- `(:Episode)-[:INVOLVED]->(:ProtocolRef)`
- `(:Episode)-[:HAD_TAG]->(:Tag)`
- `(:Mistake)-[:FROM_EPISODE]->(:Episode)`
- `(:Mistake)-[:CAUSED_BY_TAG]->(:Tag)`
- `(:Rule)-[:DERIVED_FROM]->(:Mistake)`
- `(:User)-[:HAS_POSITION]->(:Position)`
- `(:User)-[:HAS_SESSION]->(:Session)-[:HAS_TURN]->(:Turn)`

## Important

- The initialization script does not ingest live DeFiLlama data yet.
- Use stable IDs, source URLs, retrieval timestamps, and provenance for every curated dependency edge.
- Treat absent API fields as unknown, not as zero or false.
- The script attempts index creation and logs errors (including duplicate-index errors) instead of failing the whole bootstrap. Verify the logs on your FalkorDB version.
