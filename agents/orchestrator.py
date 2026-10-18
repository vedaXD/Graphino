"""Orchestrator coordinating Analyst, Guardian, and Executor agents.

COORDINATION ARCHITECTURE:
1. Graph-as-Blackboard: Agents coordinate through `Task` nodes in the user's
   memory graph (`mem_<user_id>`), recording each state transition and handoff edge.
2. Deterministic Rule Authority: The LLM NEVER decides a verdict; verdicts are
   produced strictly by `risk_engine.assess_proposal`.
3. Action Gate: The orchestrator mints an HMAC gate token ONLY for verdicts that permit
   an allocation (ALLOW, WARN, ALLOW_WITH_CAP). The Executor may only run paper trades
   with a valid token; without one it is refused.
4. Citation Validator: Validates finding IDs, URLs, and numbers against tool results.
   Regenerates once on failure, then falls back to a deterministic structured template.
5. Abstention: Explicitly reports unmodelled entities and data gaps.
6. Baseline Comparison: `--graph-off` flag disables all graph tools for the hackathon baseline.
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from typing import Any

from mcp_servers import defi_risk_server as risk_tools
from memory.store import UserMemoryStore
from risk_engine import gate

from .llm_client import AgentMessage, BaseLLMClient, GeminiLLMClient, StubLLMClient
from .roles import (
    ANALYST_SYSTEM_PROMPT,
    ANALYST_TOOLS,
    EXECUTOR_SYSTEM_PROMPT,
    EXECUTOR_TOOLS,
    GUARDIAN_SYSTEM_PROMPT,
    GUARDIAN_TOOLS,
)
from .validator import build_fallback_verdict_template, validate_citations

logger = logging.getLogger("bulwark.orchestrator")


class Orchestrator:
    def __init__(
        self,
        user_id: str = "default_user",
        llm_client: BaseLLMClient | None = None,
        graph_off: bool = False,
        db=None,
    ):
        self.user_id = user_id
        self.graph_off = graph_off
        self.db = db
        self.mem_store = UserMemoryStore(user_id=user_id, db=db)

        if llm_client is not None:
            self.llm = llm_client
        elif os.getenv("GEMINI_API_KEY"):
            try:
                self.llm = GeminiLLMClient()
            except Exception as e:
                logger.warning(f"Failed to initialize GeminiLLMClient ({e}), falling back to StubLLMClient.")
                self.llm = StubLLMClient()
        else:
            self.llm = StubLLMClient()

    # ---- Tool Execution Dispatcher -----------------------------------------
    def _call_tool(self, tool_name: str, args: dict[str, Any]) -> dict:
        """Dispatch tool calls to the defi-risk MCP tool implementation."""
        if tool_name == "search_protocol":
            return risk_tools.search_protocol(args.get("query", ""))
        elif tool_name == "get_protocol_profile":
            return risk_tools.get_protocol_profile(args.get("protocol_id", ""))
        elif tool_name == "simulate_shock":
            return risk_tools.simulate_shock(
                node=args.get("node", ""),
                severity=float(args.get("severity", 1.0)),
                max_hops=int(args.get("max_hops", 3)),
                positions=args.get("positions"),
            )
        elif tool_name == "portfolio_exposure":
            return risk_tools.portfolio_exposure(
                positions=args.get("positions", []),
                capital_usd=args.get("capital_usd"),
            )
        elif tool_name == "systemic_importance":
            return risk_tools.systemic_importance(node=args.get("node", ""))
        elif tool_name == "assess_proposal":
            return risk_tools.assess_proposal(
                proposal=args.get("proposal", {}),
                positions=args.get("positions"),
                user_id=self.user_id,
                capital_usd=args.get("capital_usd"),
            )
        elif tool_name == "execute_paper_trade":
            return risk_tools.execute_paper_trade(
                proposal=args.get("proposal", {}),
                gate_token=args.get("gate_token", ""),
                user_id=self.user_id,
            )
        raise ValueError(f"Unknown tool: {tool_name}")

    # ---- Orchestrator Execution Flow ---------------------------------------
    def run_proposal(
        self,
        proposal: dict,
        positions: list[dict] | None = None,
        execute: bool = False,
    ) -> dict:
        """Run complete 3-role risk guardian pipeline on a proposal.

        Args:
            proposal: Dict with `protocol_id` (str) and `amount_usd` (float).
            positions: Optional existing portfolio positions.
            execute: If True and the verdict allows, executes paper trade via gate.

        Returns:
            Comprehensive evaluation record.
        """
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        proto = proposal.get("protocol_id", "").strip()
        amt = float(proposal.get("amount_usd", 0.0))

        # 1. Initialize Task node in user's memory graph
        self.mem_store.create_task(
            task_id=task_id,
            from_role="user",
            to_role="analyst",
            status="proposed",
            proposal=proposal,
        )

        # ---- BASELINE CHECK: --graph-off mode ----
        if self.graph_off:
            return self._run_graph_off_baseline(task_id, proposal, positions)

        # ---- STEP 1: Analyst Role (Gather Connected Context) ----
        # The analyst queries the graph for facts, dependency trees, and contagion paths
        search_res = self._call_tool("search_protocol", {"query": proto})
        profile = self._call_tool("get_protocol_profile", {"protocol_id": proto}) if search_res.get("found") else None
        exposure = None
        if positions:
            exposure = self._call_tool("portfolio_exposure", {"positions": [*positions, proposal]})

        # Handoff task in memory graph: analyst -> guardian
        self.mem_store.handoff_task(
            task_id=task_id,
            from_role="analyst",
            to_role="guardian",
            new_status="analyzed",
            payload_ref=json.dumps(profile or search_res, default=str),
        )

        # ---- STEP 2: Guardian Role (Assess Proposal & Formulate Verdict) ----
        # Rule engine evaluation (verdicts come strictly from assess_proposal)
        verdict = self._call_tool(
            "assess_proposal",
            {"proposal": proposal, "positions": positions, "user_id": self.user_id},
        )

        # Guardian explains the verdict
        guardian_prompt = (
            f"A user proposed allocating ${amt:,.2f} to `{proto}`.\n"
            f"Here is the protocol profile: {json.dumps(profile, default=str)}\n"
            f"Here is the deterministic risk engine verdict: {json.dumps(verdict, default=str)}\n\n"
            "Explain the verdict clearly according to your instructions. Cite finding IDs, paths, and URLs."
        )

        guardian_msg = self.llm.generate(
            messages=[AgentMessage(role="user", content=guardian_prompt)],
            system_instruction=GUARDIAN_SYSTEM_PROMPT,
        )
        explanation = guardian_msg.content

        # Handoff task in memory graph: guardian -> orchestrator
        self.mem_store.handoff_task(
            task_id=task_id,
            from_role="guardian",
            to_role="orchestrator",
            new_status="evaluated",
            payload_ref=json.dumps(verdict, default=str),
        )

        # ---- STEP 3: Citation Validator & Abstention Notice ----
        is_valid, violations = validate_citations(
            text=explanation,
            proposal=proposal,
            verdict=verdict,
            profile=profile,
            exposure=exposure,
            positions=positions,
        )

        if not is_valid:
            logger.info(f"Validator detected unsupported citations ({violations}). Retrying once...")
            retry_prompt = (
                f"{guardian_prompt}\n\n"
                f"CORRECTION: Your previous answer had unsupported claims: {violations}.\n"
                "You must cite ONLY the exact URLs, finding IDs, and numbers present in the verdict JSON."
            )
            retry_msg = self.llm.generate(
                messages=[AgentMessage(role="user", content=retry_prompt)],
                system_instruction=GUARDIAN_SYSTEM_PROMPT,
            )
            retry_valid, retry_violations = validate_citations(
                text=retry_msg.content,
                proposal=proposal,
                verdict=verdict,
                profile=profile,
                exposure=exposure,
                positions=positions,
            )
            if retry_valid:
                explanation = retry_msg.content
                violations = []
            else:
                logger.warning("Second validation check failed. Falling back to deterministic structured template.")
                explanation = build_fallback_verdict_template(verdict, proposal, profile)
        elif not explanation or len(explanation.strip()) < 20:
            explanation = build_fallback_verdict_template(verdict, proposal, profile)

        # Check Abstention requirements
        data_gaps = verdict.get("coverage", {}).get("data_gaps", [])
        is_unknown = verdict.get("reason") == "unknown_protocol"
        has_abstention = is_unknown or len(data_gaps) > 0

        if has_abstention and "Abstention" not in explanation and "not modelled" not in explanation.lower():
            gap_summary = ", ".join(data_gaps) if data_gaps else f"Protocol '{proto}' is not modelled."
            explanation += (
                f"\n\n> **⚠️ Abstention Notice**: {gap_summary}. "
                "Absence of evidence in the graph is not evidence of safety."
            )

        # ---- STEP 4: Orchestrator Gate Decision & Executor Role ----
        outcome = verdict.get("outcome")
        gate_token = None
        trade_result = None

        if outcome == "BLOCK":
            # Token is NOT issued
            self.mem_store.handoff_task(
                task_id=task_id,
                from_role="orchestrator",
                to_role="executor",
                new_status="blocked",
                payload_ref="BLOCK verdict: no token issued",
            )
        else:
            # Issue HMAC gate token for ALLOW / WARN / ALLOW_WITH_CAP
            gate_ticket = gate.issue(verdict)
            if gate_ticket.get("issued"):
                gate_token = gate_ticket["token"]
                approved_amt = gate_ticket["approved_amount_usd"]

                if execute:
                    # Handoff task to executor
                    self.mem_store.handoff_task(
                        task_id=task_id,
                        from_role="orchestrator",
                        to_role="executor",
                        new_status="executing",
                        payload_ref=gate_token,
                    )

                    # Executor calls execute_paper_trade
                    trade_proposal = {**proposal, "amount_usd": approved_amt}
                    trade_result = self._call_tool(
                        "execute_paper_trade",
                        {"proposal": trade_proposal, "gate_token": gate_token},
                    )

                    self.mem_store.handoff_task(
                        task_id=task_id,
                        from_role="executor",
                        to_role="user",
                        new_status="executed",
                        payload_ref=json.dumps(trade_result, default=str),
                    )

        # ---- STEP 5: Record Interaction Episode in User Memory Graph ----
        decision_str = "executed" if (trade_result and trade_result.get("success")) else ("blocked" if outcome == "BLOCK" else "evaluated")
        self.mem_store.record_episode(
            proposal=proposal,
            verdict=verdict,
            decision=decision_str,
            outcome=explanation[:300],
        )

        return {
            "task_id": task_id,
            "user_id": self.user_id,
            "proposal": proposal,
            "verdict": verdict,
            "explanation": explanation,
            "gate_token": gate_token,
            "trade_result": trade_result,
            "violations_corrected": violations,
            "abstention_active": has_abstention,
            "graph_off": False,
        }

    def _run_graph_off_baseline(
        self,
        task_id: str,
        proposal: dict,
        positions: list[dict] | None = None,
    ) -> dict:
        """Run ungrounded LLM baseline with graph tools disabled for demo comparison."""
        proto = proposal.get("protocol_id", "unknown")
        amt = proposal.get("amount_usd", 0.0)

        prompt = (
            f"A user wants to allocate ${amt:,.2f} to DeFi protocol `{proto}`.\n"
            "Evaluate whether this is safe or risky and give your recommendation."
        )

        # Call LLM without graph tools
        resp = self.llm.generate(
            messages=[AgentMessage(role="user", content=prompt)],
            system_instruction="You are a general cryptocurrency AI assistant. Answer from your general knowledge.",
        )

        self.mem_store.handoff_task(
            task_id=task_id,
            from_role="user",
            to_role="unassisted_llm",
            new_status="graph_off_baseline",
            payload_ref="Graph tools disabled",
        )

        return {
            "task_id": task_id,
            "user_id": self.user_id,
            "proposal": proposal,
            "verdict": None,
            "explanation": resp.content,
            "gate_token": None,
            "trade_result": None,
            "violations_corrected": [],
            "abstention_active": False,
            "graph_off": True,
            "baseline_note": "Graph tools disabled: response is based solely on parametric LLM memory without graph verification.",
        }
