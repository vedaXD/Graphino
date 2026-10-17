import json
from pathlib import Path
from dotenv import load_dotenv
import os
from falkordb import FalkorDB

load_dotenv()
db = FalkorDB(
    host=os.getenv("FALKORDB_HOST", "localhost"),
    port=int(os.getenv("FALKORDB_PORT", "6379")),
    **({"username": os.getenv("FALKORDB_USERNAME")} if os.getenv("FALKORDB_USERNAME") else {}),
    **({"password": os.getenv("FALKORDB_PASSWORD")} if os.getenv("FALKORDB_PASSWORD") else {}),
)
graph = db.select_graph(os.getenv("FALKORDB_GRAPH_RISK", "defi_risk"))

queries = {
    "nodes by label": "MATCH (n) RETURN labels(n)[0] AS label, count(*) AS count ORDER BY label",
    "relationship types": "MATCH ()-[r]->() RETURN type(r) AS relationship, count(*) AS count ORDER BY relationship",
    "sample protocols": "MATCH (p:Protocol) RETURN p.name, p.slug, p.tvl_usd ORDER BY p.tvl_usd DESC LIMIT 10",
    "sample incidents": "MATCH (i:Incident) RETURN i.name, i.date, i.amount_usd LIMIT 10",
    "sample pools": "MATCH (p:Pool) RETURN p.project, p.symbol, p.tvl_usd, p.apy LIMIT 10",
}
for title, query in queries.items():
    print(f"\n=== {title} ===")
    try:
        result = graph.query(query)
        for row in result.result_set:
            print(row)
        if not result.result_set:
            print("(no records)")
    except Exception as exc:
        print("Query failed:", exc)

summary = Path("data/processed/ingestion_summary.json")
if summary.exists():
    print("\n=== ingestion summary ===")
    print(json.dumps(json.loads(summary.read_text(encoding="utf-8")), indent=2))
