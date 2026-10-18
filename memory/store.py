"""Per-user memory store on FalkorDB.

Maintains isolated graphs named `mem_<user_id>` storing:
- Preferences (risk tolerance, avoided categories/chains, max allocation)
- Past mistakes (with vocabulary-enforced risk tags and loss amounts)
- Learned rules (promoted from mistakes; block/cap/warn)
- Episodes (historical proposals, verdicts, user decisions, outcomes)
- Paper positions (positions opened via gate)

The join between memory and the risk graph is by tag only (no cross-graph Cypher).
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any

from risk_engine.db import connect
from .schema import (
    VALID_ACTIONS,
    graph_name_for_user,
    sanitize_user_id,
    validate_tag,
)


class UserMemoryStore:
    def __init__(self, user_id: str, db=None, graph_name: str | None = None):
        self.user_id = sanitize_user_id(user_id)
        self.graph_name = graph_name or graph_name_for_user(self.user_id)
        self.db = db or connect()
        self.g = self.db.select_graph(self.graph_name)

    def _query(self, q: str, params: dict | None = None) -> list:
        res = self.g.query(q, params=params) if params else self.g.query(q)
        return res.result_set

    def ensure_user(self) -> None:
        """Ensure the User node exists in this user's graph."""
        now = time.time()
        self._query(
            "MERGE (u:User {user_id: $user_id}) "
            "ON CREATE SET u.created_at = $now",
            {"user_id": self.user_id, "now": now},
        )

    # ---- Preferences --------------------------------------------------------
    def set_preference(self, key: str, value: Any) -> dict:
        """Store or update a user preference (e.g. risk_tolerance, max_position_pct, avoid_categories)."""
        self.ensure_user()
        clean_key = key.strip()
        now = time.time()
        val_str = json.dumps(value) if not isinstance(value, (int, float, str, bool)) else str(value)
        is_json = not isinstance(value, (int, float, str, bool))

        self._query(
            "MATCH (u:User {user_id: $user_id}) "
            "MERGE (u)-[:HAS_PREFERENCE]->(p:Preference {key: $key}) "
            "SET p.value = $val, p.is_json = $is_json, p.updated_at = $now",
            {"user_id": self.user_id, "key": clean_key, "val": val_str, "is_json": is_json, "now": now},
        )
        return {"key": clean_key, "value": value, "updated_at": now}

    def get_preferences(self) -> dict[str, Any]:
        """Load all preferences for this user."""
        rows = self._query(
            "MATCH (u:User {user_id: $user_id})-[:HAS_PREFERENCE]->(p:Preference) "
            "RETURN p.key, p.value, p.is_json",
            {"user_id": self.user_id},
        )
        prefs: dict[str, Any] = {}
        for r in rows:
            k, v, is_json = r[0], r[1], r[2]
            if is_json:
                try:
                    prefs[k] = json.loads(v)
                except Exception:
                    prefs[k] = v
            else:
                # Try parsing as float/int if possible
                try:
                    if "." in v:
                        prefs[k] = float(v)
                    else:
                        prefs[k] = int(v)
                except (ValueError, TypeError):
                    if v.lower() == "true":
                        prefs[k] = True
                    elif v.lower() == "false":
                        prefs[k] = False
                    else:
                        prefs[k] = v
        return prefs

    # ---- Mistakes -----------------------------------------------------------
    def record_mistake(
        self,
        tag: str,
        summary: str,
        loss_usd: float = 0.0,
        episode_id: str | None = None,
    ) -> dict:
        """Record a past mistake. The tag must belong to TAG_VOCABULARY."""
        self.ensure_user()
        valid_tag = validate_tag(tag)
        mistake_id = f"m_{uuid.uuid4().hex[:8]}"
        now = time.time()

        self._query(
            "MATCH (u:User {user_id: $user_id}) "
            "CREATE (m:Mistake {id: $id, tag: $tag, summary: $summary, "
            "loss_usd: $loss_usd, date: $now, created_at: $now}) "
            "MERGE (u)-[:MADE_MISTAKE]->(m)",
            {
                "user_id": self.user_id,
                "id": mistake_id,
                "tag": valid_tag,
                "summary": summary.strip(),
                "loss_usd": float(loss_usd),
                "now": now,
            },
        )

        if episode_id:
            self._query(
                "MATCH (e:Episode {id: $ep_id}), (m:Mistake {id: $m_id}) "
                "MERGE (e)-[:RESULTED_IN]->(m)",
                {"ep_id": episode_id, "m_id": mistake_id},
            )

        # Count total mistakes for this tag to auto-suggest rule promotion if >= 2
        count_rows = self._query(
            "MATCH (u:User {user_id: $user_id})-[:MADE_MISTAKE]->(m:Mistake {tag: $tag}) "
            "RETURN count(m)",
            {"user_id": self.user_id, "tag": valid_tag},
        )
        count = count_rows[0][0] if count_rows else 1

        # Check if an active rule already exists for this tag
        rule_rows = self._query(
            "MATCH (u:User {user_id: $user_id})-[:HAS_RULE]->(r:LearnedRule {tag: $tag, status: 'active'}) "
            "RETURN count(r)",
            {"user_id": self.user_id, "tag": valid_tag},
        )
        has_rule = bool(rule_rows and rule_rows[0][0] > 0)

        suggestion = None
        if count >= 2 and not has_rule:
            suggested_action = "block" if float(loss_usd) >= 10000.0 else "cap"
            suggestion = {
                "tag": valid_tag,
                "mistake_count": count,
                "suggested_action": suggested_action,
                "suggested_cap_pct": 5.0 if suggested_action == "cap" else None,
                "reason": (
                    f"You have recorded {count} mistakes involving '{valid_tag}'. "
                    f"Would you like to promote a protective rule to {suggested_action} such protocols?"
                ),
            }

        return {
            "id": mistake_id,
            "tag": valid_tag,
            "summary": summary.strip(),
            "loss_usd": float(loss_usd),
            "date": now,
            "tag_mistake_count": count,
            "promotion_suggestion": suggestion,
        }

    def list_mistakes(self) -> list[dict]:
        """List all recorded mistakes for this user."""
        rows = self._query(
            "MATCH (u:User {user_id: $user_id})-[:MADE_MISTAKE]->(m:Mistake) "
            "RETURN m.id, m.tag, m.summary, m.loss_usd, m.date "
            "ORDER BY m.date DESC",
            {"user_id": self.user_id},
        )
        return [
            {
                "id": r[0],
                "tag": r[1],
                "summary": r[2],
                "loss_usd": float(r[3] or 0.0),
                "date": float(r[4] or 0.0),
            }
            for r in rows
        ]

    # ---- Learned Rules ------------------------------------------------------
    def promote_rule(
        self,
        mistake_id: str,
        action: str = "block",
        cap_pct: float | None = None,
        note: str | None = None,
    ) -> dict:
        """Promote a recorded mistake into an active LearnedRule.

        The rule will be applied by assess_proposal (rule R7) on future evaluations.
        """
        self.ensure_user()
        act = action.strip().lower()
        if act not in VALID_ACTIONS:
            raise ValueError(f"Action '{action}' must be one of {VALID_ACTIONS}")

        # Find the mistake
        rows = self._query(
            "MATCH (u:User {user_id: $user_id})-[:MADE_MISTAKE]->(m:Mistake {id: $m_id}) "
            "RETURN m.tag, m.summary, m.loss_usd",
            {"user_id": self.user_id, "m_id": mistake_id},
        )
        if not rows:
            raise ValueError(f"Mistake '{mistake_id}' not found for user '{self.user_id}'.")

        tag, summary, loss = rows[0][0], rows[0][1], rows[0][2]
        rule_id = f"r_{uuid.uuid4().hex[:8]}"
        now = time.time()
        final_note = note.strip() if note else f"Learned from past loss ({summary})"
        final_cap = float(cap_pct) if act == "cap" and cap_pct is not None else (5.0 if act == "cap" else None)

        self._query(
            "MATCH (u:User {user_id: $user_id})-[:MADE_MISTAKE]->(m:Mistake {id: $m_id}) "
            "CREATE (r:LearnedRule {id: $r_id, tag: $tag, action: $action, "
            "cap_pct: $cap_pct, note: $note, status: 'active', "
            "created_from: $m_id, created_at: $now}) "
            "MERGE (u)-[:HAS_RULE]->(r) "
            "MERGE (r)-[:DERIVED_FROM]->(m)",
            {
                "user_id": self.user_id,
                "m_id": mistake_id,
                "r_id": rule_id,
                "tag": tag,
                "action": act,
                "cap_pct": final_cap,
                "note": final_note,
                "now": now,
            },
        )

        return {
            "id": rule_id,
            "tag": tag,
            "action": act,
            "cap_pct": final_cap,
            "note": final_note,
            "created_from": mistake_id,
            "status": "active",
        }

    def list_rules(self, active_only: bool = True) -> list[dict]:
        """List learned rules in the exact dictionary format expected by assess_proposal."""
        rows = self._query(
            "MATCH (u:User {user_id: $user_id})-[:HAS_RULE]->(r:LearnedRule) "
            "WHERE ($active_only = false OR r.status = 'active') "
            "RETURN r.id, r.tag, r.action, r.cap_pct, r.note, r.status "
            "ORDER BY r.created_at DESC",
            {"user_id": self.user_id, "active_only": active_only},
        )
        rules = []
        for r in rows:
            rules.append({
                "id": r[0],
                "tag": r[1],
                "action": r[2],
                "cap_pct": float(r[3]) if r[3] is not None else None,
                "note": r[4] or "",
                "status": r[5],
            })
        return rules

    def forget(self, rule_id: str) -> dict:
        """Deactivate a learned rule so it no longer fires."""
        now = time.time()
        res = self._query(
            "MATCH (u:User {user_id: $user_id})-[:HAS_RULE]->(r:LearnedRule {id: $rule_id}) "
            "SET r.status = 'inactive', r.deactivated_at = $now "
            "RETURN count(r)",
            {"user_id": self.user_id, "rule_id": rule_id, "now": now},
        )
        deactivated = bool(res and res[0][0] > 0)
        return {"rule_id": rule_id, "deactivated": deactivated}

    # ---- Episodes & Sessions ------------------------------------------------
    def record_episode(
        self,
        proposal: dict,
        verdict: dict,
        decision: str,
        outcome: str = "",
        session_id: str | None = None,
    ) -> dict:
        """Record an episode representing an evaluation and decision."""
        self.ensure_user()
        ep_id = f"ep_{uuid.uuid4().hex[:8]}"
        now = time.time()
        proto = proposal.get("protocol_id", "unknown")
        amt = float(proposal.get("amount_usd", 0.0))
        verdict_outcome = verdict.get("outcome", "UNKNOWN")

        self._query(
            "MATCH (u:User {user_id: $user_id}) "
            "CREATE (e:Episode {id: $id, protocol_id: $proto, amount_usd: $amt, "
            "verdict_outcome: $outcome_v, decision: $decision, outcome_notes: $outcome_n, "
            "proposal_json: $prop_j, verdict_json: $verdict_j, timestamp: $now}) "
            "MERGE (u)-[:EXPERIENCED]->(e)",
            {
                "user_id": self.user_id,
                "id": ep_id,
                "proto": proto,
                "amt": amt,
                "outcome_v": verdict_outcome,
                "decision": decision,
                "outcome_n": outcome,
                "prop_j": json.dumps(proposal),
                "verdict_j": json.dumps(verdict, default=str),
                "now": now,
            },
        )

        if session_id:
            self._query(
                "MATCH (u:User {user_id: $user_id}), (e:Episode {id: $ep_id}) "
                "MERGE (u)-[:HAS_SESSION]->(s:Session {session_id: $sess_id, user_id: $user_id}) "
                "MERGE (s)-[:INCLUDES_EPISODE]->(e)",
                {"user_id": self.user_id, "ep_id": ep_id, "sess_id": session_id},
            )

        return {
            "id": ep_id,
            "protocol_id": proto,
            "amount_usd": amt,
            "verdict_outcome": verdict_outcome,
            "decision": decision,
            "timestamp": now,
        }

    # ---- Paper Positions ----------------------------------------------------
    def record_paper_trade(self, trade: dict) -> dict:
        """Record an open paper position in the user's memory graph."""
        self.ensure_user()
        now = time.time()
        trade_id = trade.get("trade_id") or f"pt_{uuid.uuid4().hex[:8]}"
        proto = trade.get("protocol_id", "unknown")
        amt = float(trade.get("amount_usd", 0.0))
        chain = trade.get("chain")

        self._query(
            "MATCH (u:User {user_id: $user_id}) "
            "CREATE (p:Position {trade_id: $trade_id, protocol_id: $proto, "
            "amount_usd: $amt, chain: $chain, opened_at: $now, status: 'OPEN'}) "
            "MERGE (u)-[:HOLDS_POSITION]->(p)",
            {
                "user_id": self.user_id,
                "trade_id": trade_id,
                "proto": proto,
                "amt": amt,
                "chain": chain,
                "now": now,
            },
        )
        return {"trade_id": trade_id, "status": "OPEN", "protocol_id": proto, "amount_usd": amt}

    def get_portfolio(self) -> list[dict]:
        """Fetch all currently open paper positions."""
        rows = self._query(
            "MATCH (u:User {user_id: $user_id})-[:HOLDS_POSITION]->(p:Position) "
            "WHERE p.status = 'OPEN' "
            "RETURN p.trade_id, p.protocol_id, p.amount_usd, p.chain, p.opened_at",
            {"user_id": self.user_id},
        )
        return [
            {
                "trade_id": r[0],
                "protocol_id": r[1],
                "amount_usd": float(r[2] or 0.0),
                "chain": r[3],
                "opened_at": float(r[4] or 0.0),
            }
            for r in rows
        ]

    # ---- Task Coordination (Handoffs) ---------------------------------------
    def create_task(
        self,
        task_id: str,
        from_role: str,
        to_role: str,
        status: str,
        proposal: dict,
        payload_ref: str | None = None,
    ) -> dict:
        """Create a Task node representing agent coordination handoffs."""
        self.ensure_user()
        now = time.time()
        self._query(
            "MATCH (u:User {user_id: $user_id}) "
            "CREATE (t:Task {id: $id, from_role: $from_r, to_role: $to_r, "
            "status: $status, proposal_json: $prop_j, payload_ref: $pref, "
            "created_at: $now, updated_at: $now}) "
            "MERGE (u)-[:HAS_TASK]->(t)",
            {
                "user_id": self.user_id,
                "id": task_id,
                "from_r": from_role,
                "to_r": to_role,
                "status": status,
                "prop_j": json.dumps(proposal),
                "pref": payload_ref or "",
                "now": now,
            },
        )
        return {
            "task_id": task_id,
            "from_role": from_role,
            "to_role": to_role,
            "status": status,
            "proposal": proposal,
            "payload_ref": payload_ref,
        }

    def handoff_task(
        self,
        task_id: str,
        from_role: str,
        to_role: str,
        new_status: str,
        payload_ref: str | None = None,
    ) -> dict:
        """Record a handoff transition on a Task node and record the HANDOFF edge."""
        now = time.time()
        self._query(
            "MATCH (u:User {user_id: $user_id})-[:HAS_TASK]->(t:Task {id: $id}) "
            "SET t.from_role = $from_r, t.to_role = $to_r, t.status = $status, "
            "t.payload_ref = $pref, t.updated_at = $now "
            "CREATE (t)-[:HANDOFF {from_role: $from_r, to_role: $to_r, timestamp: $now}]->(t)",
            {
                "user_id": self.user_id,
                "id": task_id,
                "from_r": from_role,
                "to_r": to_role,
                "status": new_status,
                "pref": payload_ref or "",
                "now": now,
            },
        )
        return {
            "task_id": task_id,
            "from_role": from_role,
            "to_role": to_role,
            "status": new_status,
            "payload_ref": payload_ref,
        }

    def get_task(self, task_id: str) -> dict | None:
        rows = self._query(
            "MATCH (u:User {user_id: $user_id})-[:HAS_TASK]->(t:Task {id: $id}) "
            "RETURN t.id, t.from_role, t.to_role, t.status, t.proposal_json, t.payload_ref",
            {"user_id": self.user_id, "id": task_id},
        )
        if not rows:
            return None
        r = rows[0]
        try:
            prop = json.loads(r[4])
        except Exception:
            prop = {}
        return {
            "task_id": r[0],
            "from_role": r[1],
            "to_role": r[2],
            "status": r[3],
            "proposal": prop,
            "payload_ref": r[5],
        }

    def list_tasks(self) -> list[dict]:
        rows = self._query(
            "MATCH (u:User {user_id: $user_id})-[:HAS_TASK]->(t:Task) "
            "RETURN t.id, t.from_role, t.to_role, t.status, t.proposal_json, t.payload_ref "
            "ORDER BY t.created_at DESC",
            {"user_id": self.user_id},
        )
        tasks = []
        for r in rows:
            try:
                prop = json.loads(r[4])
            except Exception:
                prop = {}
            tasks.append({
                "task_id": r[0],
                "from_role": r[1],
                "to_role": r[2],
                "status": r[3],
                "proposal": prop,
                "payload_ref": r[5],
            })
        return tasks

    # ---- Context loading for assess_proposal --------------------------------
    def load_context(self) -> dict:
        """Load {prefs, memory_rules, mistakes} in the exact shape assess_proposal accepts."""
        return {
            "prefs": self.get_preferences(),
            "memory_rules": self.list_rules(active_only=True),
            "mistakes": self.list_mistakes(),
        }


# ---- Standalone Helper Functions --------------------------------------------
def load_context(user_id: str, db=None) -> dict:
    return UserMemoryStore(user_id=user_id, db=db).load_context()


def set_preference(user_id: str, key: str, value: Any, db=None) -> dict:
    return UserMemoryStore(user_id=user_id, db=db).set_preference(key, value)


def record_mistake(user_id: str, tag: str, summary: str, loss_usd: float = 0.0, db=None) -> dict:
    return UserMemoryStore(user_id=user_id, db=db).record_mistake(tag, summary, loss_usd)


def promote_rule(user_id: str, mistake_id: str, action: str = "block", cap_pct: float | None = None, note: str | None = None, db=None) -> dict:
    return UserMemoryStore(user_id=user_id, db=db).promote_rule(mistake_id, action, cap_pct, note)


def list_rules(user_id: str, db=None) -> list[dict]:
    return UserMemoryStore(user_id=user_id, db=db).list_rules()


def forget(user_id: str, rule_id: str, db=None) -> dict:
    return UserMemoryStore(user_id=user_id, db=db).forget(rule_id)


def record_episode(user_id: str, proposal: dict, verdict: dict, decision: str, outcome: str = "", session_id: str | None = None, db=None) -> dict:
    return UserMemoryStore(user_id=user_id, db=db).record_episode(proposal, verdict, decision, outcome, session_id)


def record_paper_trade(user_id: str, trade: dict, db=None) -> dict:
    return UserMemoryStore(user_id=user_id, db=db).record_paper_trade(trade)


def get_portfolio(user_id: str, db=None) -> list[dict]:
    return UserMemoryStore(user_id=user_id, db=db).get_portfolio()
