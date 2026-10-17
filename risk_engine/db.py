"""FalkorDB connection. Reads only: the risk engine never writes to defi_risk."""
from __future__ import annotations

from . import config as C


def connect():
    """Return a FalkorDB client. Uses the embedded FalkorDBLite when
    FALKORDB_LITE_PATH is set (tests), otherwise the Docker/Cloud instance."""
    if C.FALKORDB_LITE_PATH:
        from redislite.falkordb_client import FalkorDB  # pip install falkordblite

        return FalkorDB(C.FALKORDB_LITE_PATH)
    from falkordb import FalkorDB  # pip install FalkorDB

    return FalkorDB(
        host=C.FALKORDB_HOST,
        port=C.FALKORDB_PORT,
        username=C.FALKORDB_USERNAME,
        password=C.FALKORDB_PASSWORD,
    )


def ro(graph, query: str, params: dict | None = None):
    """Read-only query (GRAPH.RO_QUERY). Values go in `params`; only validated
    integers (traversal depth) are ever formatted into query text."""
    res = graph.ro_query(query, params=params) if params else graph.ro_query(query)
    return res.result_set
