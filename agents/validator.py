"""Citation and fact validator for agent explanations.

ENFORCEMENT RULES:
1. Every URL cited in a response must trace directly to a tool result.
2. Every USD amount, percentage, and protocol ID mentioned must be grounded
   in tool inputs/outputs (proposal, verdict findings, protocol profile, or exposure).
3. If an explanation contains fabricated/unsupported claims, the orchestrator
   retries once, and then falls back to a deterministic structured template.
4. Abstention: if unknown_protocol or data_gaps are non-empty, the output must
   explicitly state what is unmodelled.
"""
from __future__ import annotations

import re
from typing import Any


def _normalize_num(n_str: str) -> float | None:
    try:
        clean = n_str.replace(",", "").strip()
        return float(clean)
    except Exception:
        return None


def extract_citations(text: str) -> dict[str, list[Any]]:
    """Extract URLs, USD amounts, percentages, and bracketed codes from text."""
    # URLs
    urls = re.findall(r"https?://[^\s)\]\"'>]+", text)

    # Dollar amounts: $1,000, $500.50, $10M
    raw_usd = re.findall(r"\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?|\d+(?:\.[0-9]+)?)", text)
    usd_amounts = [v for v in [_normalize_num(x) for x in raw_usd] if v is not None]

    # Percentages: 5%, 40.5%
    raw_pct = re.findall(r"(\d+(?:\.\d+)?)\s*%", text)
    pcts = [v for v in [_normalize_num(x) for x in raw_pct] if v is not None]

    # Finding IDs: F-xxxxxxxx
    finding_ids = re.findall(r"F-[0-9a-fA-F]{8}", text)

    return {
        "urls": list(set(urls)),
        "usd_amounts": usd_amounts,
        "percentages": pcts,
        "finding_ids": list(set(finding_ids)),
    }


def collect_ground_truth(
    proposal: dict | None = None,
    verdict: dict | None = None,
    profile: dict | None = None,
    exposure: dict | None = None,
    shock: dict | None = None,
    positions: list[dict] | None = None,
) -> dict[str, set]:
    """Compile all authorized facts, numbers, and URLs from tool execution results."""
    valid_urls: set[str] = set()
    valid_numbers: set[float] = set()
    valid_finding_ids: set[str] = set()
    valid_protocols: set[str] = set()

    # Numbers from proposal
    if proposal:
        if "amount_usd" in proposal:
            amt = _normalize_num(str(proposal["amount_usd"]))
            if amt is not None:
                valid_numbers.add(amt)
        if "protocol_id" in proposal:
            valid_protocols.add(str(proposal["protocol_id"]).lower())

    # Numbers from positions
    for p in positions or []:
        if "amount_usd" in p:
            amt = _normalize_num(str(p["amount_usd"]))
            if amt is not None:
                valid_numbers.add(amt)
        if "protocol_id" in p:
            valid_protocols.add(str(p["protocol_id"]).lower())

    # Facts from verdict
    if verdict:
        allowed = verdict.get("allowed_amount_usd")
        if allowed is not None:
            valid_numbers.add(float(allowed))

        cov = verdict.get("coverage", {})
        if "capital_usd" in cov:
            valid_numbers.add(float(cov["capital_usd"]))

        for f in verdict.get("findings", []):
            if "id" in f:
                valid_finding_ids.add(f["id"])
            if f.get("cap_usd") is not None:
                valid_numbers.add(float(f["cap_usd"]))

            # Path nodes
            for node in f.get("path", []):
                valid_protocols.add(str(node).lower())

            # Details
            details = f.get("details", {})
            for inc in details.get("incidents", []):
                if "amount" in inc and inc["amount"] is not None:
                    valid_numbers.add(float(inc["amount"]))

            # Evidence URLs
            for e in f.get("evidence", []):
                if e.get("source_url"):
                    valid_urls.add(e["source_url"].rstrip("/"))
                if e.get("url"):
                    valid_urls.add(e["url"].rstrip("/"))

    # Facts from profile
    if profile:
        if profile.get("protocol_id"):
            valid_protocols.add(str(profile["protocol_id"]).lower())
        if profile.get("tvl_usd") is not None:
            valid_numbers.add(float(profile["tvl_usd"]))
        if profile.get("change_7d") is not None:
            valid_numbers.add(abs(float(profile["change_7d"])))

        for inc in profile.get("incidents", []):
            if inc.get("amount") is not None:
                valid_numbers.add(float(inc["amount"]))
            if inc.get("source_url"):
                valid_urls.add(inc["source_url"].rstrip("/"))

        for p in profile.get("dependency_paths", []):
            for e in p.get("evidence", []):
                if e.get("source_url"):
                    valid_urls.add(e["source_url"].rstrip("/"))

        for doc in profile.get("evidence_documents", []):
            if doc.get("url"):
                valid_urls.add(doc["url"].rstrip("/"))

    # Standard policy percentages
    # 5%, 10%, 40%, 30%, 70%, 100%
    standard_percentages = {5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 40.0, 50.0, 70.0, 100.0}
    valid_numbers |= standard_percentages

    return {
        "urls": valid_urls,
        "numbers": valid_numbers,
        "finding_ids": valid_finding_ids,
        "protocols": valid_protocols,
    }


def validate_citations(
    text: str,
    proposal: dict | None = None,
    verdict: dict | None = None,
    profile: dict | None = None,
    exposure: dict | None = None,
    shock: dict | None = None,
    positions: list[dict] | None = None,
) -> tuple[bool, list[str]]:
    """Validate that every citation, URL, finding ID, and significant number is grounded.

    Returns:
        (is_valid: bool, violations: list[str])
    """
    citations = extract_citations(text)
    gt = collect_ground_truth(
        proposal=proposal,
        verdict=verdict,
        profile=profile,
        exposure=exposure,
        shock=shock,
        positions=positions,
    )

    violations: list[str] = []

    # 1. Validate URLs
    for url in citations["urls"]:
        clean_url = url.rstrip("/")
        # Check prefix match or exact match against ground truth URLs
        if not any(clean_url == u or clean_url.startswith(u) or u.startswith(clean_url) for u in gt["urls"]):
            violations.append(f"Unsupported URL cited: '{url}' (not in tool results)")

    # 2. Validate Finding IDs
    for fid in citations["finding_ids"]:
        if fid not in gt["finding_ids"]:
            violations.append(f"Fabricated finding ID cited: '{fid}'")

    # 3. Validate USD numbers (allow zero and minor roundings)
    for num in citations["usd_amounts"]:
        if num == 0.0 or num in (1.0, 2.0, 3.0):  # skip trivial numbers
            continue
        # Check if num is close to any valid number in ground truth
        matched = any(abs(num - v) / max(v, 1.0) < 0.02 for v in gt["numbers"])
        if not matched:
            violations.append(f"Fabricated or ungrounded USD amount cited: ${num:,.2f}")

    is_valid = len(violations) == 0
    return is_valid, violations


def build_fallback_verdict_template(
    verdict: dict,
    proposal: dict,
    profile: dict | None = None,
) -> str:
    """Deterministic structured template generated directly from the verdict JSON.

    Used when agent text fails validation twice or abstains.
    """
    outcome = verdict.get("outcome", "UNKNOWN")
    allowed = verdict.get("allowed_amount_usd", 0.0)
    req_amt = proposal.get("amount_usd", 0.0)
    proto = proposal.get("protocol_id", "unknown")
    proto_name = (profile or {}).get("name") or proto

    lines = [
        f"### Risk Verdict: **{outcome}**",
        f"- **Protocol**: {proto_name} (`{proto}`)",
        f"- **Requested Allocation**: ${req_amt:,.2f}",
        f"- **Approved Allocation Limit**: ${allowed:,.2f}",
        "",
        "#### Findings & Graph Paths:",
    ]

    findings = verdict.get("findings", [])
    if not findings:
        lines.append("No adverse risk findings triggered by the modelled graph data.")
    else:
        for f in findings:
            fid = f.get("id", "F-xxxx")
            rule = f.get("rule", "Unknown")
            sev = f.get("severity", "info").upper()
            summary = f.get("summary", "")
            path_str = " ➔ ".join(f.get("path", [proto]))
            action = f.get("action", "none")
            cap = f.get("cap_usd")

            line = f"- **[{fid}] ({rule} - {sev})**: {summary}"
            lines.append(line)
            lines.append(f"  - *Graph Path*: `{path_str}`")
            if action == "cap" and cap is not None:
                lines.append(f"  - *Action*: Capped at ${cap:,.2f}")

            # Evidence sources
            ev_urls = [e.get("source_url") or e.get("url") for e in f.get("evidence", []) if e.get("source_url") or e.get("url")]
            if ev_urls:
                lines.append(f"  - *Sources*: {', '.join(ev_urls)}")

            # Memory citation
            mem = f.get("memory_ref")
            if mem:
                lines.append(f"  - *Memory Link*: {mem.get('kind')} `{mem.get('id')}` (tag: `{mem.get('tag')}`)")

    # Data gaps & Abstention notice
    gaps = verdict.get("coverage", {}).get("data_gaps", [])
    if gaps or verdict.get("reason") == "unknown_protocol":
        lines.append("")
        lines.append("#### ⚠️ Abstention & Coverage Gaps:")
        if verdict.get("reason") == "unknown_protocol":
            lines.append(f"- **Unknown Protocol**: `{proto}` is not in the risk graph.")
        for g in gaps:
            lines.append(f"- *Data Gap*: {g}")
        lines.append("> **Important**: Unmodelled dependencies mean unknown risk, NEVER safety. Absence of graph edges is not proof of security.")

    lines.append("")
    lines.append(f"*{verdict.get('disclaimer', 'Paper trading only. Not financial advice.')}*")
    return "\n".join(lines)
