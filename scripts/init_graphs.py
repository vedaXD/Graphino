from falkordb import FalkorDB

from src.config import (
    FALKORDB_HOST, FALKORDB_PORT, FALKORDB_USERNAME, FALKORDB_PASSWORD,
    RISK_GRAPH, EVIDENCE_GRAPH, memory_graph_name,
)
from src.graph_schema import INDEX_STATEMENTS

def connect():
    kwargs = {"host": FALKORDB_HOST, "port": FALKORDB_PORT}
    if FALKORDB_USERNAME:
        kwargs["username"] = FALKORDB_USERNAME
    if FALKORDB_PASSWORD:
        kwargs["password"] = FALKORDB_PASSWORD
    return FalkorDB(**kwargs)

def run_query(graph, query):
    return graph.query(query)

def initialize_graph(db, graph_name, indexes, graph_kind):
    graph = db.select_graph(graph_name)
    # A write creates the graph if it does not yet exist.
    run_query(
        graph,
        "MERGE (m:GraphMeta {name: $name}) "
        "SET m.kind = $kind, m.schema_version = '1.0', "
        "m.updated_at = timestamp()",
    ) if False else None

    # Keep this first bootstrap query literal for compatibility across client versions.
    safe_name = graph_name.replace("\\", "\\\\").replace("'", "\\'")
    safe_kind = graph_kind.replace("\\", "\\\\").replace("'", "\\'")
    run_query(
        graph,
        f"MERGE (m:GraphMeta {{name: '{safe_name}'}}) "
        f"SET m.kind = '{safe_kind}', m.schema_version = '1.0', "
        "m.updated_at = timestamp()",
    )
    print(f"\n[{graph_name}] graph initialized")

    for statement in indexes:
        try:
            run_query(graph, statement)
            print(f"  index OK: {statement}")
        except Exception as exc:
            # Some server versions report an existing index as an error. Keep bootstrapping.
            print(f"  index skipped/failed: {statement}\n    reason: {exc}")

def main():
    db = connect()
    initialize_graph(db, RISK_GRAPH, INDEX_STATEMENTS["defi_risk"], "shared_risk")
    initialize_graph(db, EVIDENCE_GRAPH, INDEX_STATEMENTS["defi_evidence"], "shared_evidence")

    # Create two demo memory graphs to verify tenant isolation.
    for user_id in ("alice", "bob"):
        graph_name = memory_graph_name(user_id)
        initialize_graph(db, graph_name, INDEX_STATEMENTS["memory"], "private_user_memory")

    print("\nDone. Graphs bootstrapped:")
    print(f"  - {RISK_GRAPH}")
    print(f"  - {EVIDENCE_GRAPH}")
    print(f"  - {memory_graph_name('alice')}")
    print(f"  - {memory_graph_name('bob')}")
    print("\nNote: FalkorDB labels/relationship types are schema-flexible; indexes and GraphMeta are initialized.")

if __name__ == "__main__":
    main()
