"""Schema constants and tag validation for per-user memory graphs (mem_<user_id>)."""
from __future__ import annotations

import re
from typing import Any

from risk_engine import config as C

# User graph naming convention: mem_<user_id>
GRAPH_PREFIX = "mem_"


def sanitize_user_id(user_id: str) -> str:
    """Sanitize user_id to ensure safe FalkorDB graph naming (alphanumeric and underscore)."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", user_id.strip().lower())
    if not cleaned:
        return "default"
    return cleaned


def graph_name_for_user(user_id: str) -> str:
    """Compute FalkorDB graph name for a given user."""
    return f"{GRAPH_PREFIX}{sanitize_user_id(user_id)}"


def validate_tag(tag: str) -> str:
    """Validate that tag belongs strictly to the controlled TAG_VOCABULARY.

    The join between memory and risk graphs happens by tag only.
    No cross-graph Cypher is used.
    """
    clean_tag = tag.strip().lower()
    if clean_tag not in C.TAG_VOCABULARY:
        raise ValueError(
            f"Invalid tag '{tag}'. Tag must be in TAG_VOCABULARY: {sorted(C.TAG_VOCABULARY)}"
        )
    return clean_tag


# Valid rule actions
VALID_ACTIONS = ("block", "cap", "warn")
