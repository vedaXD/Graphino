import os
from dotenv import load_dotenv

load_dotenv()

FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
FALKORDB_USERNAME = os.getenv("FALKORDB_USERNAME") or None
FALKORDB_PASSWORD = os.getenv("FALKORDB_PASSWORD") or None

RISK_GRAPH = os.getenv("FALKORDB_GRAPH_RISK", "defi_risk")
EVIDENCE_GRAPH = os.getenv("FALKORDB_GRAPH_EVIDENCE", "defi_evidence")
MEMORY_PREFIX = os.getenv("FALKORDB_GRAPH_MEMORY_PREFIX", "mem_")

def memory_graph_name(user_id: str) -> str:
    """Create a safe, deterministic per-user graph name."""
    safe_id = "".join(c for c in user_id.lower() if c.isalnum() or c in "_-")
    if not safe_id:
        raise ValueError("user_id must contain at least one alphanumeric character")
    return f"{MEMORY_PREFIX}{safe_id}"
