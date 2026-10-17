"""Small, restartable DeFiLlama -> FalkorDB ingestion pipeline for Bulwark.

It snapshots API responses under data/raw, then ingests curated node/edge types.
Candidate metadata is deliberately not converted into DEPENDS_ON edges.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from falkordb import FalkorDB

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
RAW.mkdir(parents=True, exist_ok=True)
PROCESSED.mkdir(parents=True, exist_ok=True)

API = "https://api.llama.fi"
STABLECOIN_API = "https://stablecoins.llama.fi"
YIELD_API = "https://yields.llama.fi"

HOST = os.getenv("FALKORDB_HOST", "localhost")
PORT = int(os.getenv("FALKORDB_PORT", "6379"))
USERNAME = os.getenv("FALKORDB_USERNAME") or None
PASSWORD = os.getenv("FALKORDB_PASSWORD") or None
GRAPH_NAME = os.getenv("FALKORDB_GRAPH_RISK", "defi_risk")
PROTOCOL_LIMIT = int(os.getenv("PROTOCOL_LIMIT", "25"))
POOL_TVL_MIN_USD = float(os.getenv("POOL_TVL_MIN_USD", "10000000"))
POOLS_PER_PROTOCOL = int(os.getenv("POOLS_PER_PROTOCOL", "5"))
HTTP_TIMEOUT = int(os.getenv("HTTP_TIMEOUT", "45"))

# Category quotas encourage a connected, varied demo graph.
CATEGORY_QUOTAS = [
    ("Lending", 5),
    ("Dexes", 5),
    ("Liquid Staking", 4),
    ("CDP", 3),
    ("Yield", 3),
    ("Derivatives", 3),
    ("Bridge", 2),
]
EXCLUDE_NAME_PARTS = ("cex", "centralized exchange", "centralised exchange")

session = requests.Session()
session.headers.update({"User-Agent": "Bulwark-GraphIngestion/1.0 (hackathon demo)"})


def api_get(url: str, cache_name: str, pause: float = 0.0) -> Any:
    """Download and cache JSON; use cache if network is temporarily unavailable."""
    cache_path = RAW / cache_name
    if pause:
        time.sleep(pause)
    try:
        response = session.get(url, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        payload = response.json()
        cache_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        print(f"[HTTP {response.status_code}] {url}")
        return payload
    except Exception as exc:
        if cache_path.exists():
            print(f"[WARN] {url} failed ({exc}); using cached {cache_path.name}")
            return json.loads(cache_path.read_text(encoding="utf-8"))
        raise RuntimeError(f"Request failed and no cache exists: {url}\n{exc}") from exc


def connect_graph():
    kwargs = {"host": HOST, "port": PORT}
    if USERNAME:
        kwargs["username"] = USERNAME
    if PASSWORD:
        kwargs["password"] = PASSWORD
    db = FalkorDB(**kwargs)
    return db.select_graph(GRAPH_NAME)


def scalar(value: Any) -> Any:
    """Convert values to FalkorDB-safe scalar/list properties."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, list):
        if all(v is None or isinstance(v, (str, int, float, bool)) for v in value):
            return [v for v in value if v is not None]
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def props(data: dict, allowed: list[str] | None = None) -> dict:
    result = {}
    for key, value in data.items():
        if allowed is not None and key not in allowed:
            continue
        if value is None:
            continue
        # Avoid nested dict/list properties that FalkorDB cannot store directly.
        result[key] = scalar(value)
    return result


def upsert_node(graph, label: str, key_name: str, key_value: Any, properties: dict):
    if key_value is None or str(key_value).strip() == "":
        return
    safe_props = {k: v for k, v in properties.items() if k != key_name}
    query = (
        f"MERGE (n:{label} {{{key_name}: $key_value}}) "
        "SET n += $properties"
    )
    graph.query(query, {"key_value": scalar(key_value), "properties": safe_props})


def upsert_edge(graph, left_label: str, left_key: str, left_value: Any,
                rel_type: str, right_label: str, right_key: str, right_value: Any,
                properties: dict | None = None):
    if left_value is None or right_value is None:
        return
    query = (
        f"MATCH (a:{left_label} {{{left_key}: $left_value}}), "
        f"(b:{right_label} {{{right_key}: $right_value}}) "
        f"MERGE (a)-[r:{rel_type}]->(b) "
        "SET r += $properties"
    )
    graph.query(query, {
        "left_value": scalar(left_value),
        "right_value": scalar(right_value),
        "properties": properties or {},
    })


def numeric(value):
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def protocol_slug(record: dict) -> str | None:
    slug = record.get("slug")
    if slug:
        return str(slug).strip().lower()
    module = record.get("module")
    if module:
        return str(module).strip().lower()
    return None


def is_excluded(record: dict) -> bool:
    name = str(record.get("name", "")).lower()
    category = str(record.get("category", "")).lower()
    return (
        any(part in name for part in EXCLUDE_NAME_PARTS)
        or category in {"cex", "centralized exchange", "centralised exchange"}
        or not protocol_slug(record)
    )


def select_protocols(records: list[dict]) -> list[dict]:
    valid = [r for r in records if not is_excluded(r)]
    # De-duplicate by slug and prioritize TVL within each category.
    by_slug = {}
    for r in valid:
        slug = protocol_slug(r)
        if slug and slug not in by_slug:
            by_slug[slug] = r
    valid = list(by_slug.values())
    valid.sort(key=lambda r: numeric(r.get("tvl")) or 0, reverse=True)

    selected, seen = [], set()
    for category, quota in CATEGORY_QUOTAS:
        candidates = [
            r for r in valid
            if str(r.get("category", "")).lower() == category.lower()
        ]
        added = 0
        for r in candidates:
            slug = protocol_slug(r)
            if slug in seen:
                continue
            selected.append(r)
            seen.add(slug)
            added += 1
            if added >= quota:
                break

    # Fill any category shortfall from the highest-TVL remaining non-CEX protocols.
    for r in valid:
        if len(selected) >= PROTOCOL_LIMIT:
            break
        slug = protocol_slug(r)
        if slug not in seen:
            selected.append(r)
            seen.add(slug)

    selected = selected[:PROTOCOL_LIMIT]
    (PROCESSED / "selected_protocols.json").write_text(
        json.dumps(selected, indent=2), encoding="utf-8"
    )
    print(f"Selected {len(selected)} protocols (target {PROTOCOL_LIMIT}).")
    print("Categories:", {c: sum(1 for r in selected if str(r.get("category", "")).lower() == c.lower())
                           for c, _ in CATEGORY_QUOTAS})
    return selected


def select_chains(chains: list[dict], selected_protocols: list[dict], limit: int = 8) -> list[dict]:
    """Select up to eight chains used by the chosen protocols, preferring coverage and TVL."""
    usage = {}
    for protocol in selected_protocols:
        names = protocol.get("chains") or ([protocol.get("chain")] if protocol.get("chain") else [])
        for name in names:
            if name:
                key = str(name).lower()
                usage[key] = usage.get(key, 0) + 1

    candidates = []
    for item in chains:
        name = item.get("name")
        if not name or str(name).lower() not in usage:
            continue
        # Prefer chains used by many selected protocols, then by TVL.
        candidates.append((usage[str(name).lower()], numeric(item.get("tvl")) or 0, item))
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    chosen = [row[2] for row in candidates[:limit]]

    # Fallback for a sparse/odd protocol metadata response.
    if len(chosen) < min(limit, 6):
        for item in sorted(chains, key=lambda x: numeric(x.get("tvl")) or 0, reverse=True):
            if item.get("name") and all(str(item["name"]).lower() != str(c.get("name", "")).lower() for c in chosen):
                chosen.append(item)
            if len(chosen) >= limit:
                break

    (PROCESSED / "selected_chains.json").write_text(
        json.dumps(chosen, indent=2), encoding="utf-8"
    )
    print(f"Selected {len(chosen)} chains (target up to {limit}).")
    return chosen


def ingest_chains(graph, chains: list[dict]) -> dict[str, dict]:
    lookup = {}
    for item in chains:
        name = item.get("name")
        if not name:
            continue
        chain_id = item.get("chainId")
        chain_key = str(chain_id) if chain_id is not None else str(name).lower().replace(" ", "-")
        data = {
            "chain_id": chain_key,
            "name": str(name),
            "chain_id_numeric": chain_id,
            "token_symbol": item.get("tokenSymbol"),
            "gecko_id": item.get("gecko_id"),
            "tvl_usd": numeric(item.get("tvl")),
            "source_url": f"{API}/v2/chains",
        }
        upsert_node(graph, "Chain", "chain_id", chain_key, props(data))
        lookup[str(name).lower()] = {"chain_id": chain_key, "name": str(name)}
    print(f"Ingested/updated {len(lookup)} selected chains.")
    return lookup


def ingest_protocol_base(graph, selected: list[dict], chain_lookup: dict):
    selected_slugs = set()
    for record in selected:
        slug = protocol_slug(record)
        if not slug:
            continue
        selected_slugs.add(slug)
        data = {
            "protocol_id": str(record.get("id") or slug),
            "slug": slug,
            "name": record.get("name"),
            "category": record.get("category"),
            "symbol": record.get("symbol"),
            "url": record.get("url"),
            "description": record.get("description"),
            "listed_at": record.get("listedAt"),
            "tvl_usd": numeric(record.get("tvl")),
            "chains": record.get("chains") or ([record.get("chain")] if record.get("chain") else []),
            "source_url": f"{API}/protocol/{slug}",
            "retrieved_at": int(time.time()),
        }
        upsert_node(graph, "Protocol", "slug", slug, props(data))
        for chain_name in data["chains"] or []:
            chain = chain_lookup.get(str(chain_name).lower())
            if chain:
                upsert_edge(
                    graph, "Protocol", "slug", slug,
                    "DEPLOYED_ON", "Chain", "chain_id", chain["chain_id"],
                    {"source_url": f"{API}/protocol/{slug}", "confidence": 1.0},
                )
    print(f"Ingested/updated {len(selected_slugs)} protocol nodes.")
    return selected_slugs


def iter_named_assets(value):
    """Yield conservative token candidates from inconsistent API shapes."""
    if value is None:
        return
    if isinstance(value, dict):
        # A dictionary might be one token record or a keyed token map.
        if any(k in value for k in ("symbol", "name", "id", "gecko_id", "address")):
            yield value
        else:
            for k, v in value.items():
                if isinstance(v, dict):
                    item = dict(v)
                    item.setdefault("symbol", k)
                    yield item
                elif isinstance(v, (str, int, float)):
                    yield {"symbol": k, "name": str(v)}
    elif isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                yield item
            elif isinstance(item, str):
                yield {"symbol": item}


def asset_key(asset: dict, prefix: str = "token") -> str | None:
    ident = asset.get("id") or asset.get("gecko_id") or asset.get("address")
    if ident:
        return f"{prefix}:{str(ident).lower()}"
    symbol = asset.get("symbol") or asset.get("name")
    if symbol:
        return f"{prefix}:{str(symbol).lower()}"
    return None


def ingest_protocol_details(graph, selected: list[dict], chain_lookup: dict):
    detail_count = 0
    incident_count = 0
    related_count = 0
    asset_count = 0
    for i, record in enumerate(selected, start=1):
        slug = protocol_slug(record)
        if not slug:
            continue
        detail = api_get(f"{API}/protocol/{slug}", f"protocol_{slug}.json", pause=0.15)
        detail_count += 1
        # Enrich protocol node, retaining the full raw response in data/raw.
        update = {
            "slug": slug,
            "name": detail.get("name") or record.get("name"),
            "description": detail.get("description"),
            "url": detail.get("url") or record.get("url"),
            "symbol": detail.get("symbol") or record.get("symbol"),
            "category": detail.get("category") or record.get("category"),
            "chains": detail.get("chains") or record.get("chains") or [],
            "governance_id": detail.get("governanceID"),
            "is_parent_protocol": detail.get("isParentProtocol"),
            "tvl_usd": numeric(record.get("tvl")),
            "source_url": f"{API}/protocol/{slug}",
            "retrieved_at": int(time.time()),
        }
        graph.query(
            "MATCH (p:Protocol {slug: $slug}) SET p += $properties",
            {"slug": slug, "properties": props(update)},
        )

        # Chains: a protocol's chain list is a deployment signal, not a dependency.
        for chain_name in detail.get("chains") or []:
            chain = chain_lookup.get(str(chain_name).lower())
            if chain:
                upsert_edge(graph, "Protocol", "slug", slug, "DEPLOYED_ON",
                            "Chain", "chain_id", chain["chain_id"],
                            {"source_url": f"{API}/protocol/{slug}", "confidence": 1.0})

        # Token/stablecoin associations are ingested as candidate metadata edges,
        # not DEPENDS_ON edges. Inspect candidate_kind before using them for propagation.
        for field in ("tokens", "stablecoins"):
            for token in iter_named_assets(detail.get(field)):
                key = asset_key(token, prefix=field[:-1] if field.endswith("s") else field)
                if not key:
                    continue
                asset_props = {
                    "asset_id": key,
                    "name": token.get("name") or token.get("symbol") or key,
                    "symbol": token.get("symbol"),
                    "asset_type": "stablecoin_candidate" if field == "stablecoins" else "token_candidate",
                    "source_url": f"{API}/protocol/{slug}",
                    "candidate_source_field": field,
                }
                upsert_node(graph, "Asset", "asset_id", key, props(asset_props))
                rel = "ASSOCIATED_WITH_ASSET"
                upsert_edge(
                    graph, "Protocol", "slug", slug, rel, "Asset", "asset_id", key,
                    {"candidate_kind": field, "source_url": f"{API}/protocol/{slug}",
                     "verified_semantics": False},
                )
                asset_count += 1

        # Related protocols are explicitly NOT treated as dependencies.
        for related in detail.get("otherProtocols") or []:
            if isinstance(related, dict):
                other_slug = related.get("slug") or related.get("module") or related.get("name")
            else:
                other_slug = str(related)
            if not other_slug:
                continue
            other_slug = str(other_slug).strip().lower()
            if other_slug == slug:
                continue
            # Create a placeholder protocol only if the slug is among our selected protocols.
            # This avoids silently expanding the graph with ambiguous records.
            selected_slugs = {protocol_slug(r) for r in selected}
            if other_slug in selected_slugs:
                upsert_edge(
                    graph, "Protocol", "slug", slug, "RELATED_TO",
                    "Protocol", "slug", other_slug,
                    {"source_url": f"{API}/protocol/{slug}",
                     "relationship_source_field": "otherProtocols",
                     "verified_semantics": False},
                )
                related_count += 1

        # Incident records: only ingest structured objects with enough identity.
        hacks = detail.get("hacks") or []
        if isinstance(hacks, dict):
            hacks = [hacks]
        if isinstance(hacks, list):
            for idx, hack in enumerate(hacks):
                if not isinstance(hack, dict):
                    continue
                incident_name = hack.get("name") or hack.get("title") or f"{detail.get('name', slug)} incident"
                incident_date = hack.get("date")
                incident_id = f"{slug}:{incident_date or 'undated'}:{idx}"
                incident_props = {
                    "incident_id": incident_id,
                    "name": incident_name,
                    "date": incident_date,
                    "classification": hack.get("classification") or hack.get("technique"),
                    "amount_usd": numeric(hack.get("amount")),
                    "chain": hack.get("chain"),
                    "source_url": hack.get("source") or f"{API}/protocol/{slug}",
                    "source_protocol_slug": slug,
                    "retrieved_at": int(time.time()),
                }
                upsert_node(graph, "Incident", "incident_id", incident_id, props(incident_props))
                upsert_edge(
                    graph, "Protocol", "slug", slug, "AFFECTED_BY",
                    "Incident", "incident_id", incident_id,
                    {"source_url": incident_props["source_url"],
                     "relationship_basis": "protocol_hacks_field"},
                )
                incident_count += 1

        if i % 5 == 0 or i == len(selected):
            print(f"  protocol detail {i}/{len(selected)} processed")
    print(f"Detail records: {detail_count}; candidate asset associations: {asset_count}; "
          f"related-protocol candidates: {related_count}; incident records: {incident_count}")


def ingest_stablecoins(graph, payload, limit: int = 10):
    assets = payload.get("peggedAssets", []) if isinstance(payload, dict) else []
    if not isinstance(assets, list):
        print("[WARN] stablecoins.peggedAssets is not a list; skipping stablecoin ingestion.")
        return 0

    # Prefer familiar, demo-relevant assets when present; fill remaining slots by circulation.
    preferred_symbols = ["USDT", "USDC", "DAI", "USDS", "USDE", "FRAX", "TUSD", "USDD", "LUSD", "USDX"]
    def circulation_score(item):
        value = item.get("circulating")
        if isinstance(value, dict):
            return sum(numeric(v) or 0 for v in value.values())
        return numeric(value) or 0

    by_symbol = {str(a.get("symbol", "")).upper(): a for a in assets if isinstance(a, dict)}
    chosen = []
    seen_ids = set()
    for symbol in preferred_symbols:
        item = by_symbol.get(symbol)
        if item:
            ident = item.get("id") or item.get("gecko_id") or item.get("name") or item.get("symbol")
            if ident is not None and str(ident) not in seen_ids:
                chosen.append(item)
                seen_ids.add(str(ident))
            if len(chosen) >= limit:
                break
    if len(chosen) < limit:
        for item in sorted([a for a in assets if isinstance(a, dict)], key=circulation_score, reverse=True):
            ident = item.get("id") or item.get("gecko_id") or item.get("name") or item.get("symbol")
            if ident is None or str(ident) in seen_ids:
                continue
            chosen.append(item)
            seen_ids.add(str(ident))
            if len(chosen) >= limit:
                break

    count = 0
    for item in chosen:
        if not isinstance(item, dict):
            continue
        ident = item.get("id") or item.get("gecko_id") or item.get("name") or item.get("symbol")
        if not ident:
            continue
        key = f"stablecoin:{str(ident).lower()}"
        data = {
            "asset_id": key,
            "name": item.get("name"),
            "symbol": item.get("symbol"),
            "asset_type": "stablecoin",
            "peg_type": item.get("pegType") or item.get("pegType"),
            "peg_mechanism": item.get("pegMechanism"),
            "gecko_id": item.get("gecko_id"),
            "source_url": f"{STABLECOIN_API}/stablecoins",
            "retrieved_at": int(time.time()),
        }
        # Retain a compact JSON string for changing nested schemas.
        for field in ("chains", "circulating", "price", "pegMechanism"):
            if field in item and item[field] is not None:
                data[f"raw_{field}"] = scalar(item[field])
        upsert_node(graph, "Asset", "asset_id", key, props(data))
        count += 1
    print(f"Ingested/updated {count} stablecoin assets.")
    return count


def ingest_pools(graph, payload, selected_slugs: set[str]):
    records = payload.get("data", []) if isinstance(payload, dict) else []
    if not isinstance(records, list):
        print("[WARN] pools.data is not a list; skipping pools.")
        return 0
    grouped = {}
    for pool in records:
        if not isinstance(pool, dict):
            continue
        project = str(pool.get("project") or "").lower()
        tvl = numeric(pool.get("tvlUsd")) or 0
        if project not in selected_slugs or tvl < POOL_TVL_MIN_USD:
            continue
        grouped.setdefault(project, []).append(pool)

    selected_pools = []
    for project, items in grouped.items():
        items.sort(key=lambda p: numeric(p.get("tvlUsd")) or 0, reverse=True)
        selected_pools.extend(items[:POOLS_PER_PROTOCOL])

    count = 0
    for pool in selected_pools:
        project = str(pool.get("project") or "").lower()
        pool_id = pool.get("pool")
        if not pool_id:
            # Fallback stable-ish identifier for records without a pool UUID.
            pool_id = f"{project}:{pool.get('chain')}:{pool.get('symbol')}"
        pool_id = str(pool_id)
        data = {
            "pool_id": pool_id,
            "project": project,
            "chain": pool.get("chain"),
            "symbol": pool.get("symbol"),
            "tvl_usd": numeric(pool.get("tvlUsd")),
            "apy_base": numeric(pool.get("apyBase")),
            "apy_reward": numeric(pool.get("apyReward")),
            "apy": numeric(pool.get("apy")),
            "il_risk": pool.get("ilRisk"),
            "outlier": pool.get("outlier"),
            "stablecoin": pool.get("stablecoin"),
            "exposure": pool.get("exposure"),
            "underlying_tokens": pool.get("underlyingTokens"),
            "source_url": f"{YIELD_API}/pools",
            "retrieved_at": int(time.time()),
        }
        upsert_node(graph, "Pool", "pool_id", pool_id, props(data))
        upsert_edge(
            graph, "Protocol", "slug", project, "HAS_POOL",
            "Pool", "pool_id", pool_id,
            {"source_url": f"{YIELD_API}/pools"},
        )
        # Link pool to known chain by name if chain metadata exists.
        if pool.get("chain"):
            chain_key = str(pool["chain"]).lower()
            # Find a chain by its display name; no edge if the name doesn't match.
            try:
                result = graph.query(
                    "MATCH (c:Chain) WHERE toLower(c.name) = $name RETURN c.chain_id LIMIT 1",
                    {"name": chain_key},
                )
                if result.result_set:
                    chain_id = result.result_set[0][0]
                    upsert_edge(graph, "Pool", "pool_id", pool_id, "ON_CHAIN",
                                "Chain", "chain_id", chain_id,
                                {"source_url": f"{YIELD_API}/pools"})
            except Exception as exc:
                print(f"[WARN] pool-chain link skipped for {pool_id}: {exc}")
        count += 1

    (PROCESSED / "selected_pools.json").write_text(
        json.dumps(selected_pools, indent=2), encoding="utf-8"
    )
    print(f"Ingested/updated {count} pools (TVL >= ${POOL_TVL_MIN_USD:,.0f}; "
          f"max {POOLS_PER_PROTOCOL} per selected protocol).")
    return count


def write_summary(summary: dict):
    path = PROCESSED / "ingestion_summary.json"
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\nSummary saved to {path.relative_to(ROOT)}")
    print(json.dumps(summary, indent=2))


def main():
    print(f"Connecting to FalkorDB {HOST}:{PORT}, graph={GRAPH_NAME}")
    graph = connect_graph()

    protocols_raw = api_get(f"{API}/protocols", "protocols.json")
    chains_raw = api_get(f"{API}/v2/chains", "chains.json")
    stablecoins_raw = api_get(f"{STABLECOIN_API}/stablecoins", "stablecoins.json")
    pools_raw = api_get(f"{YIELD_API}/pools", "pools.json")

    if not isinstance(protocols_raw, list):
        raise TypeError("/protocols response was not a JSON list")
    if not isinstance(chains_raw, list):
        raise TypeError("/v2/chains response was not a JSON list")

    selected = select_protocols(protocols_raw)
    selected_chains = select_chains(chains_raw, selected, limit=8)
    chain_lookup = ingest_chains(graph, selected_chains)
    selected_slugs = ingest_protocol_base(graph, selected, chain_lookup)
    stablecoin_count = ingest_stablecoins(graph, stablecoins_raw, limit=10)
    ingest_protocol_details(graph, selected, chain_lookup)
    pool_count = ingest_pools(graph, pools_raw, selected_slugs)

    summary = {
        "graph": GRAPH_NAME,
        "selected_protocols": len(selected_slugs),
        "chains_seen": len(chain_lookup),
        "stablecoin_assets": stablecoin_count,
        "pools_ingested": pool_count,
        "protocol_detail_requests": len(selected_slugs),
        "api_snapshot_files": [
            "data/raw/protocols.json",
            "data/raw/chains.json",
            "data/raw/stablecoins.json",
            "data/raw/pools.json",
            "data/processed/selected_chains.json",
        ],
        "important_semantics": [
            "DEPLOYED_ON comes from the protocol chains field.",
            "otherProtocols is stored as RELATED_TO only and is not a DEPENDS_ON edge.",
            "token/stablecoin associations are candidate metadata links, not verified dependency edges.",
            "hacks records are ingested only when structured incident objects are present.",
            "Oracle, bridge, controller, auditor and verified DEPENDS_ON edges remain for curated sourced ingestion.",
        ],
    }
    write_summary(summary)


if __name__ == "__main__":
    main()
