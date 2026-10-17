from falkordb import FalkorDB
from src.config import (
    FALKORDB_HOST, FALKORDB_PORT, FALKORDB_USERNAME, FALKORDB_PASSWORD,
    RISK_GRAPH, EVIDENCE_GRAPH, memory_graph_name,
)

def connect():
    kwargs = {"host": FALKORDB_HOST, "port": FALKORDB_PORT}
    if FALKORDB_USERNAME:
        kwargs["username"] = FALKORDB_USERNAME
    if FALKORDB_PASSWORD:
        kwargs["password"] = FALKORDB_PASSWORD
    return FalkorDB(**kwargs)

def main():
    db = connect()
    names = [RISK_GRAPH, EVIDENCE_GRAPH, memory_graph_name("alice"), memory_graph_name("bob")]
    for name in names:
        graph = db.select_graph(name)
        print(f"\n=== {name} ===")
        try:
            result = graph.query("MATCH (n) RETURN labels(n) AS labels, count(*) AS count")
            for row in result.result_set:
                print(row)
        except Exception as exc:
            print("Could not inspect graph:", exc)
        try:
            result = graph.query("MATCH (n:GraphMeta) RETURN n.name, n.kind, n.schema_version")
            for row in result.result_set:
                print("GraphMeta:", row)
        except Exception as exc:
            print("GraphMeta query failed:", exc)

if __name__ == "__main__":
    main()
