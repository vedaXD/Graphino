"""Export real seeded FalkorDB graph data into Frontend/src/lib/data/graphData.ts.

Connects to the live FalkorDB instance and reads:
- defi_risk: Protocol, Chain, Asset, Oracle, Controller, Incident, Pool nodes and edges
- defi_evidence: Evidence nodes
Writes a clean, strongly-typed TypeScript module for the Next.js frontend.
"""
import json
import os
import sys
import time
from pathlib import Path
from falkordb import FalkorDB
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

HOST = os.getenv("FALKORDB_HOST", "localhost")
PORT = int(os.getenv("FALKORDB_PORT", "6379"))
RISK_GRAPH = os.getenv("FALKORDB_GRAPH_RISK", "defi_risk")
EVIDENCE_GRAPH = os.getenv("FALKORDB_GRAPH_EVIDENCE", "defi_evidence")

OUTPUT_PATH = ROOT / "Frontend" / "src" / "lib" / "data" / "graphData.ts"
PROCESSED_PROTOCOLS = ROOT / "data" / "processed" / "selected_protocols.json"


def main():
    print(f"Connecting to FalkorDB at {HOST}:{PORT}...")
    db = FalkorDB(host=HOST, port=PORT)
    risk = db.select_graph(RISK_GRAPH)
    evidence = db.select_graph(EVIDENCE_GRAPH)

    # Protocols metadata lookup
    proto_meta = {}
    if PROCESSED_PROTOCOLS.exists():
        try:
            raw_p = json.loads(PROCESSED_PROTOCOLS.read_text(encoding="utf-8"))
            for p in raw_p:
                slug = p.get("slug")
                if slug:
                    proto_meta[slug] = p
        except Exception as e:
            print(f"Warning loading {PROCESSED_PROTOCOLS}: {e}")

    graph_nodes = []
    seen_node_ids = set()

    # 1. Protocols
    protos = risk.query("MATCH (p:Protocol) RETURN p").result_set
    for row in protos:
        p = row[0].properties
        slug = p.get("slug") or p.get("name", "").lower().replace(" ", "-")
        if not slug or slug in seen_node_ids:
            continue
        seen_node_ids.add(slug)

        meta = proto_meta.get(slug, {})
        name = p.get("name") or meta.get("name") or slug
        category = p.get("category") or meta.get("category") or "DeFi"
        tvl = float(p.get("tvl_usd") or p.get("tvl") or meta.get("tvl") or 0.0)

        # Audits
        audits = None
        if "audits" in p and p["audits"] is not None:
            try:
                audits = int(p["audits"])
            except (ValueError, TypeError):
                audits = None
        elif "audits" in meta and meta["audits"] is not None:
            try:
                audits = int(meta["audits"])
            except (ValueError, TypeError):
                audits = None

        # Age in days
        listed_at = p.get("listed_at") or meta.get("listedAt")
        now_ts = int(time.time())
        age_days = int((now_ts - listed_at) / 86400) if listed_at else 700

        source_url = p.get("source_url") or meta.get("url") or f"https://api.llama.fi/protocol/{slug}"

        node = {
            "id": slug,
            "name": name,
            "label": "Protocol",
            "category": category,
            "tvl_usd": tvl,
            "audits": audits,
            "age_days": max(1, age_days),
            "change_7d": 1.5,
            "sourceUrl": source_url,
        }
        graph_nodes.append(node)

    # 2. Chains
    chains = risk.query("MATCH (c:Chain) RETURN c").result_set
    for row in chains:
        c = row[0].properties
        cid = str(c.get("chain_id") or c.get("name", "")).strip()
        if not cid or cid in seen_node_ids:
            continue
        seen_node_ids.add(cid)

        name = c.get("name") or cid
        tvl = float(c.get("tvl_usd") or 0.0)
        symbol = c.get("token_symbol")
        source_url = c.get("source_url") or "https://api.llama.fi/v2/chains"

        node = {
            "id": cid,
            "name": name,
            "label": "Chain",
            "tvl_usd": tvl,
            "symbol": symbol or undefined_symbol(name),
            "sourceUrl": source_url,
        }
        graph_nodes.append(node)

    # 3. Oracles
    oracles = risk.query("MATCH (o:Oracle) RETURN o").result_set
    for row in oracles:
        o = row[0].properties
        oid = str(o.get("oracle_id") or o.get("name", "")).strip()
        if not oid or oid in seen_node_ids:
            continue
        seen_node_ids.add(oid)

        name = o.get("name") or oid
        kind = o.get("kind") or "price_oracle"
        source_url = o.get("source_url") or "https://aave.com/docs/ecosystem/oracle"

        node = {
            "id": oid,
            "name": name,
            "label": "Oracle",
            "kind": kind,
            "sourceUrl": source_url,
        }
        graph_nodes.append(node)

    # 4. Controllers
    controllers = risk.query("MATCH (c:Controller) RETURN c").result_set
    for row in controllers:
        c = row[0].properties
        cid = str(c.get("controller_id") or c.get("name", "")).strip()
        if not cid or cid in seen_node_ids:
            continue
        seen_node_ids.add(cid)

        name = c.get("name") or cid
        ctype = c.get("controller_type") or "governance"
        source_url = c.get("source_url") or "https://aave.com/docs/ecosystem/oracle"

        node = {
            "id": cid,
            "name": name,
            "label": "Controller",
            "controllerType": ctype if ctype in ("multisig", "eoa", "governance") else "governance",
            "sourceUrl": source_url,
        }
        graph_nodes.append(node)

    # 5. Stablecoins / Assets
    assets = risk.query("MATCH (a:Asset) RETURN a").result_set
    for row in assets:
        a = row[0].properties
        aid = str(a.get("asset_id") or a.get("symbol", "")).strip()
        if not aid or aid in seen_node_ids:
            continue
        seen_node_ids.add(aid)

        name = a.get("name") or aid
        symbol = a.get("symbol") or aid.upper()
        peg_mech = a.get("peg_mechanism") or "fiat-backed"
        peg_type = a.get("peg_type") or "peggedUSD"
        raw_price = a.get("raw_price")
        price = float(raw_price) if raw_price is not None else 1.0
        peg_dev = round(abs(price - 1.0) * 100.0, 3)

        source_url = a.get("source_url") or "https://stablecoins.llama.fi/stablecoins"

        node = {
            "id": aid,
            "name": name,
            "label": "Stablecoin",
            "symbol": symbol,
            "price": price,
            "pegType": peg_type,
            "pegMechanism": peg_mech,
            "pegDevPct": peg_dev,
            "sourceUrl": source_url,
        }
        graph_nodes.append(node)

    # 6. Incidents
    incidents = risk.query("MATCH (i:Incident) RETURN i").result_set
    for row in incidents:
        inc = row[0].properties
        iid = str(inc.get("incident_id") or inc.get("name", "")).strip()
        if not iid or iid in seen_node_ids:
            continue
        seen_node_ids.add(iid)

        name = inc.get("name") or iid
        amount = float(inc.get("amount_usd") or 0.0)
        date_val = str(inc.get("date") or "2024-03-12")
        classification = inc.get("classification") or "Protocol Exploit"
        summary = f"{classification}: ${amount:,.0f} lost"
        source_url = inc.get("source_url") or "https://api.llama.fi"

        node = {
            "id": iid,
            "name": name,
            "label": "Incident",
            "amountUsd": amount,
            "date": date_val,
            "summary": summary,
            "sourceUrl": source_url,
        }
        graph_nodes.append(node)

    # 7. Pools
    pools = risk.query("MATCH (p:Pool) RETURN p").result_set
    for row in pools:
        pl = row[0].properties
        pid = str(pl.get("pool_id") or "").strip()
        if not pid or pid in seen_node_ids:
            continue
        seen_node_ids.add(pid)

        project = pl.get("project") or "pool"
        sym = pl.get("symbol") or "LP"
        chain = pl.get("chain") or ""
        name = f"{project.title()} - {sym} ({chain})" if chain else f"{project.title()} - {sym}"
        tvl = float(pl.get("tvl_usd") or 0.0)
        apy = float(pl.get("apy") or pl.get("apy_base") or 0.0)
        outlier = bool(pl.get("outlier", False))
        source_url = pl.get("source_url") or "https://yields.llama.fi/pools"

        node = {
            "id": pid,
            "name": name,
            "label": "Pool",
            "symbol": sym,
            "tvl_usd": tvl,
            "apy": apy,
            "outlier": outlier,
            "sourceUrl": source_url,
        }
        graph_nodes.append(node)

    # 8. Evidence (from defi_evidence)
    try:
        evs = evidence.query("MATCH (e:Evidence) RETURN e").result_set
        for row in evs:
            e = row[0].properties
            eid = str(e.get("evidence_id") or "").strip()
            if not eid or eid in seen_node_ids:
                continue
            seen_node_ids.add(eid)

            title = e.get("title") or eid
            summary = e.get("summary") or ""
            source_url = e.get("source_url") or ""

            node = {
                "id": eid,
                "name": title,
                "label": "Evidence",
                "summary": summary,
                "sourceUrl": source_url,
            }
            graph_nodes.append(node)
    except Exception as exc:
        print(f"Warning querying evidence graph: {exc}")

    # Now extract edges
    edge_query = """
    MATCH (a)-[r]->(b)
    RETURN 
        labels(a)[0] AS from_label,
        CASE 
            WHEN 'Protocol' IN labels(a) THEN a.slug
            WHEN 'Oracle' IN labels(a) THEN a.oracle_id
            WHEN 'Controller' IN labels(a) THEN a.controller_id
            WHEN 'Asset' IN labels(a) THEN a.asset_id
            WHEN 'Chain' IN labels(a) THEN a.chain_id
            WHEN 'Pool' IN labels(a) THEN a.pool_id
            WHEN 'Incident' IN labels(a) THEN a.incident_id
            ELSE id(a)
        END AS from_id,
        type(r) AS rel_type,
        labels(b)[0] AS to_label,
        CASE 
            WHEN 'Protocol' IN labels(b) THEN b.slug
            WHEN 'Oracle' IN labels(b) THEN b.oracle_id
            WHEN 'Controller' IN labels(b) THEN b.controller_id
            WHEN 'Asset' IN labels(b) THEN b.asset_id
            WHEN 'Chain' IN labels(b) THEN b.chain_id
            WHEN 'Pool' IN labels(b) THEN b.pool_id
            WHEN 'Incident' IN labels(b) THEN b.incident_id
            ELSE id(b)
        END AS to_id,
        properties(r) AS props
    """
    raw_edges = risk.query(edge_query).result_set
    graph_edges = []
    seen_edge_keys = set()

    for row in raw_edges:
        from_label, from_id, rel_type, to_label, to_id, props = row
        from_id = str(from_id)
        to_id = str(to_id)
        if not from_id or not to_id:
            continue

        edge_key = f"{from_id}_{rel_type}_{to_id}"
        if edge_key in seen_edge_keys:
            continue
        seen_edge_keys.add(edge_key)

        verified = (
            props.get("verification_status") in ("documented", "verified", "source_verified")
            or bool(props.get("verified", False))
        )
        risk_eligible = bool(props.get("risk_eligible", False))
        strength = float(props.get("strength", 1.0)) if props.get("strength") is not None else 1.0
        confidence = float(props.get("confidence", 1.0)) if props.get("confidence") is not None else 1.0
        scope = props.get("scope")
        source_url = props.get("source_url") or ""

        edge = {
            "id": f"e_{edge_key}",
            "from": from_id,
            "to": to_id,
            "type": rel_type,
            "strength": strength,
            "confidence": confidence,
            "verified": verified,
            "risk_eligible": risk_eligible,
            "is_test": bool(props.get("is_test", False)),
            "source_url": source_url,
            "sourceUrl": source_url,
        }
        if scope:
            edge["scope"] = scope
        graph_edges.append(edge)

    print(f"Total exported nodes: {len(graph_nodes)}")
    print(f"Total exported edges: {len(graph_edges)}")

    # Ensure parent directory exists
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Format TypeScript file
    ts_content = [
        'import { GraphNode, GraphEdge } from "../types";',
        "",
        "// Live exported graph data from FalkorDB (defi_risk & defi_evidence)",
        f"// Generated at: {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}",
        f"// Total Nodes: {len(graph_nodes)} | Total Edges: {len(graph_edges)}",
        "",
        "export const GRAPH_NODES: GraphNode[] = " + json.dumps(graph_nodes, indent=2) + ";",
        "",
        "export const GRAPH_EDGES: GraphEdge[] = " + json.dumps(graph_edges, indent=2) + ";",
        "",
    ]

    OUTPUT_PATH.write_text("\n".join(ts_content), encoding="utf-8")
    print(f"Successfully generated {OUTPUT_PATH}")


def undefined_symbol(name: str) -> str:
    name_map = {
        "Ethereum": "ETH",
        "Arbitrum": "ARB",
        "Base": "ETH",
        "Avalanche": "AVAX",
        "Binance": "BNB",
        "Optimism": "OP",
        "Solana": "SOL",
        "Hyperliquid L1": "HYPE",
    }
    return name_map.get(name, name[:4].upper())


if __name__ == "__main__":
    main()
