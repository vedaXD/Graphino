"""Evidence lookup in defi_evidence. Evidence lives in a separate graph and is
joined to risk entities in application code by stable slugs (no cross-graph
Cypher). Tolerant of how the link was stored: a property on the Evidence node,
or an edge to a stub node that carries the slug."""
from __future__ import annotations

from . import config as C
from .db import connect, ro
from .util import pick


class EvidenceIndex:
    def __init__(self, db=None, graph_name: str | None = None):
        self.db = db or connect()
        self.g = self.db.select_graph(graph_name or C.EVIDENCE_GRAPH)
        self.available = False
        self._items: list[dict] = []
        self._load()

    def _load(self) -> None:
        try:
            rows = ro(self.g, f"MATCH (e:`{C.EVIDENCE_LABEL}`) RETURN id(e), properties(e)")
            linked = ro(
                self.g,
                f"MATCH (e:`{C.EVIDENCE_LABEL}`)-[r]-(x) RETURN id(e), "
                "[k IN " + str(list(C.NODE_KEY_PROPS)) + " | properties(x)[k]]",
            )
        except Exception:  # graph missing / empty / label absent
            self.available = False
            return
        self.available = True
        neighbours: dict[int, set[str]] = {}
        for eid, vals in linked:
            neighbours.setdefault(eid, set()).update(str(v).lower() for v in vals if v)
        for eid, props in rows:
            props = dict(props)
            links: set[str] = set()
            for p in C.EVIDENCE_LINK_PROPS:
                v = props.get(p)
                if isinstance(v, list):
                    links.update(str(x).lower() for x in v)
                elif v:
                    links.add(str(v).lower())
            links |= neighbours.get(eid, set())
            self._items.append({
                "id": pick(props, ("id", "evidence_id")) or f"evidence-{eid}",
                "title": props.get("title"), "url": pick(props, ("url", "source_url")),
                "source_type": props.get("source_type"), "_links": links,
            })

    def for_protocol(self, slug: str) -> list[dict]:
        s = slug.lower()
        return [{k: v for k, v in it.items() if k != "_links"} for it in self._items if s in it["_links"]]
