"""ALL Cypher the risk engine depends on lives here (the hackathon requires the
queries to be documented; `python -m risk_engine.cli queries` prints them).

FalkorDB notes verified against FalkorDBLite while writing this:
  * parameters work in WHERE/properties/UNWIND, but NOT in variable-length
    bounds (`*1..$d` fails), so depth is a validated int formatted into the text;
  * `EXISTS { MATCH ... }` subqueries are not supported, so "no shared
    dependency" style checks are done in Python over returned paths;
  * `ALL(e IN relationships(path) WHERE ...)` works, which is how the
    eligibility predicate is enforced on EVERY edge of a path.
"""
from __future__ import annotations

from . import config as C
from .util import clamp_int

REL = "|".join(C.DEPENDENCY_REL_TYPES)
ALL_RISK_AND_NON = "|".join(C.DEPENDENCY_REL_TYPES + C.NON_RISK_REL_TYPES)


def key(alias: str) -> str:
    """Cypher expression for a node's identity, e.g. coalesce(n.slug, n.id, n.name)."""
    return "coalesce(" + ", ".join(f"{alias}.{p}" for p in C.NODE_KEY_PROPS) + ")"


def elig(alias: str) -> str:
    """Eligibility predicate for a relationship alias (fail-closed)."""
    return "(" + C.ELIGIBILITY_TEMPLATE.format(r=alias) + ")"


def depth(d) -> int:
    return clamp_int(d, 1, 4, C.TH["MAX_HOPS"])


# ---- node lookup / validation (names are validated against the graph) ------
def resolve(label: str | None) -> str:
    lab = f":{label}" if label else ""
    return f"MATCH (n{lab}) WHERE {key('n')} = $k RETURN labels(n), properties(n) LIMIT 1"


def did_you_mean() -> str:
    return (
        "MATCH (n:Protocol) "
        f"WHERE toLower(toString({key('n')})) CONTAINS toLower($q) "
        "OR toLower(toString(coalesce(n.name, ''))) CONTAINS toLower($q) "
        f"RETURN {key('n')}, n.name LIMIT 5"
    )


# ---- protocol facts --------------------------------------------------------
Q_CHAINS = (
    "MATCH (p:Protocol)-[:DEPLOYED_ON]->(c) "
    f"WHERE {key('p')} = $k RETURN {key('c')}"
)
Q_INCIDENTS = (
    "MATCH (p)-[:AFFECTED_BY]->(i:Incident) "
    f"WHERE {key('p')} IN $keys RETURN {key('p')}, properties(i)"
)
Q_POOLS = (
    "MATCH (p:Protocol)-[:HAS_POOL]->(pl:Pool) "
    f"WHERE {key('p')} = $k RETURN properties(pl) LIMIT 50"
)


# ---- eligible dependency paths --------------------------------------------
def _path_return(anchor: str, other: str) -> str:
    """Columns: anchor key, other key, other labels, other props, node keys along the
    path (dependent -> dependency), rel types, strengths, source urls."""
    return (
        f"{key(anchor)}, {key(other)}, labels({other}), properties({other}), "
        f"[n IN nodes(path) | {key('n')}], "
        "[e IN relationships(path) | type(e)], "
        "[e IN relationships(path) | e.strength], "
        "[e IN relationships(path) | e.source_url]"
    )


def forward_paths(d) -> str:
    """What does each protocol in $keys depend on? (multi-hop, eligible edges only)"""
    return (
        f"MATCH path = (p:Protocol)-[:{REL}*1..{depth(d)}]->(o) "
        f"WHERE {key('p')} IN $keys AND ALL(e IN relationships(path) WHERE {elig('e')}) "
        f"RETURN {_path_return('p', 'o')}"
    )


def reverse_paths(d) -> str:
    """Who breaks if node $k fails? Walk INCOMING eligible edges up to depth d."""
    return (
        f"MATCH path = (o)-[:{REL}*1..{depth(d)}]->(s) "
        f"WHERE {key('s')} = $k AND ALL(e IN relationships(path) WHERE {elig('e')}) "
        f"RETURN {_path_return('s', 'o')}"
    )


Q_ALL_ELIGIBLE_EDGES = (
    f"MATCH (a)-[e:{REL}]->(b) WHERE {elig('e')} "
    f"RETURN {key('a')}, {key('b')}, labels(a), labels(b), type(e)"
)


# ---- diagnostics (why is my output empty?) ----------------------------------
Q_EDGE_DIAG = (
    f"MATCH ()-[e:{ALL_RISK_AND_NON}]->() RETURN type(e), count(e), "
    f"sum(CASE WHEN {elig('e')} THEN 1 ELSE 0 END), "
    "sum(CASE WHEN coalesce(e.risk_eligible, false) = true THEN 1 ELSE 0 END), "
    "sum(CASE WHEN coalesce(e.verified, false) = true THEN 1 ELSE 0 END), "
    "sum(CASE WHEN coalesce(e.is_test, false) = true THEN 1 ELSE 0 END)"
)
Q_LABELS = "CALL db.labels() YIELD label RETURN label"
Q_REL_TYPES = "CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType"


def q_label_props(label: str) -> str:
    return f"MATCH (n:`{label}`) UNWIND keys(n) AS k RETURN k, count(*) ORDER BY count(*) DESC"


def q_label_count(label: str) -> str:
    return f"MATCH (n:`{label}`) RETURN count(n)"


def q_rel_props(rtype: str) -> str:
    return f"MATCH ()-[e:`{rtype}`]->() UNWIND keys(e) AS k RETURN k, count(*) ORDER BY count(*) DESC"


def all_queries() -> dict[str, str]:
    return {
        "resolve_protocol": resolve("Protocol"),
        "did_you_mean": did_you_mean(),
        "chains": Q_CHAINS,
        "incidents": Q_INCIDENTS,
        "pools": Q_POOLS,
        "forward_paths (portfolio exposure / dependencies)": forward_paths(C.TH["MAX_HOPS"]),
        "reverse_paths (shock simulation)": reverse_paths(C.TH["MAX_HOPS"]),
        "all_eligible_edges (PageRank input)": Q_ALL_ELIGIBLE_EDGES,
        "edge_diagnostics": Q_EDGE_DIAG,
    }
