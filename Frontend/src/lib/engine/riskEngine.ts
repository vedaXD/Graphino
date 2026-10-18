import { GRAPH_NODES, GRAPH_EDGES } from "../data/graphData";
import {
  Finding,
  Proposal,
  Verdict,
  GateToken,
  UserProfile,
  GraphNode,
  DependencyPath,
} from "../types";

const TOLERANCE_MULTIPLIERS = {
  conservative: 0.6,
  moderate: 1.0,
  aggressive: 1.4,
};

// Traverse eligible forward dependencies up to maxHops (default 3)
export function getEligibleDependencyPaths(
  protocolId: string,
  maxHops: number = 3
): DependencyPath[] {
  const paths: DependencyPath[] = [];
  const visited = new Set<string>();

  function dfs(
    currentId: string,
    currentHop: number,
    currentPath: string[],
    currentRels: string[],
    currentStrength: number
  ) {
    if (currentHop > maxHops) return;

    // Outgoing eligible edges
    const outgoing = GRAPH_EDGES.filter(
      (e) =>
        e.from === currentId &&
        e.verified &&
        e.risk_eligible &&
        !e.is_test
    );

    for (const edge of outgoing) {
      const targetNode = GRAPH_NODES.find((n) => n.id === edge.to);
      if (!targetNode) continue;

      const newHop = currentHop + 1;
      const newPath = [...currentPath, targetNode.id];
      const newRels = [...currentRels, edge.type];
      const newStrength = currentStrength * (edge.strength || 1.0);

      const pathKey = `${targetNode.id}_${newHop}`;
      if (!visited.has(pathKey)) {
        visited.add(pathKey);
        paths.push({
          target: targetNode.id,
          targetLabels: [targetNode.label],
          hops: newHop,
          nodes: newPath,
          relationships: newRels,
          strength: Number(newStrength.toFixed(3)),
          evidence: [
            {
              source_url: edge.sourceUrl || targetNode.sourceUrl,
              verified: edge.verified,
              strength: edge.strength,
            },
          ],
        });
      }

      dfs(targetNode.id, newHop, newPath, newRels, newStrength);
    }
  }

  dfs(protocolId, 0, [protocolId], [], 1.0);
  return paths;
}

// Find fuzzy did_you_mean suggestions if protocol is unmodelled
export function findSuggestions(query: string): string[] {
  const q = query.toLowerCase().trim();
  const protocols = GRAPH_NODES.filter((n) => n.label === "Protocol");
  return protocols
    .filter(
      (p) =>
        p.id.toLowerCase().includes(q) ||
        p.name.toLowerCase().includes(q) ||
        q.includes(p.id)
    )
    .map((p) => p.id)
    .slice(0, 3);
}

// Deterministic Risk Assessment matching risk_engine/engine.py
export function assessProposal(
  proposal: Proposal,
  userProfile: UserProfile,
  syntheticShocks: { node: string; severity: number }[] = []
): Verdict {
  const protocol = GRAPH_NODES.find(
    (n) => n.id === proposal.protocol_id && n.label === "Protocol"
  );

  // Handle Unmodelled Protocol (Fail-Closed)
  if (!protocol) {
    const suggestions = findSuggestions(proposal.protocol_id);
    return {
      outcome: "BLOCK",
      proposal,
      allowed_amount_usd: 0,
      findings: [
        {
          id: "R9_UNMODELLED",
          rule: "R9",
          severity: "high",
          message: `'${proposal.protocol_id}' is not in the risk graph. Absence from graph indicates the protocol is unmodelled, NOT safe.`,
          path: [proposal.protocol_id],
          subject: proposal.protocol_id,
          action: "block",
          cap_usd: 0,
          details: { tags: ["unmodelled_protocol"] },
        },
      ],
      tags: ["unmodelled_protocol"],
      coverage: {
        modelled: false,
        dependency_paths: 0,
        max_hops: 3,
        gaps: ["unmodelled_in_graph", "no_verified_dependencies"],
      },
      did_you_mean: suggestions,
      rules_version: "2024.10-falkordb-deterministic",
      disclaimer:
        "Deterministic policy evaluation. Unmodelled entities fail-closed. Not financial advice.",
      message: `Protocol '${proposal.protocol_id}' is not indexed in the FalkorDB risk graph.`,
    };
  }

  const findings: Finding[] = [];
  const tagsSet = new Set<string>();

  const capital = userProfile.capital_usd;
  const tolerance = userProfile.preferences.risk_tolerance || "moderate";
  const mult = TOLERANCE_MULTIPLIERS[tolerance] || 1.0;
  const depPaths = getEligibleDependencyPaths(protocol.id, 3);
  const bestDepMap = new Map<string, DependencyPath>();
  for (const dp of depPaths) {
    if (
      !bestDepMap.has(dp.target) ||
      (bestDepMap.get(dp.target)?.strength || 0) < dp.strength
    ) {
      bestDepMap.set(dp.target, dp);
    }
  }

  // Helper for tagging
  const addTag = (...tags: string[]) => tags.forEach((t) => tagsSet.add(t));

  // --- RULE R9: Coverage / Verification ---
  if (depPaths.length === 0) {
    findings.push({
      id: "R9_NO_DEPS",
      rule: "R9",
      severity: "medium",
      message: `No verified dependencies are modelled for ${protocol.name}. This represents unknown infrastructure, not proven safety.`,
      path: [protocol.id],
      subject: protocol.id,
      action: "warn",
      details: { tags: ["no_verified_dependencies"] },
    });
    addTag("no_verified_dependencies");
  }

  // --- RULE R1: Shared Dependency Concentration ---
  const limitPct = 40.0 * mult;
  const limitUsd = (capital * limitPct) / 100.0;
  const existingHoldings = userProfile.positions;

  // Check if any dependency is shared with current holdings
  for (const [depId, pathRec] of bestDepMap.entries()) {
    const exposedProtocols: string[] = [protocol.id];
    let totalExposureUsd = proposal.amount_usd * pathRec.strength;

    for (const pos of existingHoldings) {
      const posPaths = getEligibleDependencyPaths(pos.protocol_id, 3);
      const match = posPaths.find((p) => p.target === depId);
      if (match) {
        exposedProtocols.push(pos.protocol_id);
        totalExposureUsd += pos.amount_usd * match.strength;
      }
    }

    const sharePct = (totalExposureUsd / capital) * 100.0;
    if (exposedProtocols.length > 1 && sharePct > limitPct) {
      const targetNode = GRAPH_NODES.find((n) => n.id === depId);
      const depName = targetNode?.name || depId;
      findings.push({
        id: `R1_CONCENTRATION_${depId}`,
        rule: "R1",
        severity: "high",
        message: `${sharePct.toFixed(0)}% of total capital would concentrate on shared dependency '${depName}' across ${exposedProtocols.join(", ")} (limit ${limitPct.toFixed(0)}%).`,
        path: pathRec.nodes,
        subject: depId,
        action: "cap",
        cap_usd: Math.max(0, limitUsd * 0.7),
        evidence: pathRec.evidence,
        details: {
          tags: ["shared_dependency"],
          share_pct: sharePct,
          limit_pct: limitPct,
          also_exposed_via: exposedProtocols.filter((p) => p !== protocol.id),
        },
      });
      addTag("shared_dependency");
    }
  }

  // --- RULE R2: Young or Unaudited Protocol ---
  if (protocol.audits === 0) {
    const capUsd = capital * 0.05 * mult;
    findings.push({
      id: "R2_NO_AUDITS",
      rule: "R2",
      severity: "medium",
      message: `${protocol.name} lists zero verified audits in primary documentation. Absence of audit records triggers strict allocation cap.`,
      path: [protocol.id],
      subject: protocol.id,
      action: "cap",
      cap_usd: capUsd,
      details: { tags: ["unaudited_listed"] },
    });
    addTag("unaudited_listed");
  }

  if (protocol.age_days !== undefined && protocol.age_days < 90) {
    const capUsd = capital * 0.05 * mult;
    findings.push({
      id: "R2_YOUNG",
      rule: "R2",
      severity: "medium",
      message: `${protocol.name} was listed only ${protocol.age_days} days ago (< 90-day maturity threshold).`,
      path: [protocol.id],
      subject: protocol.id,
      action: "cap",
      cap_usd: capUsd,
      details: { tags: ["young_protocol"] },
    });
    addTag("young_protocol");
  }

  // --- RULE R3: Incident History (Own & Dependencies) ---
  const ownIncidents = GRAPH_EDGES.filter(
    (e) => e.from === protocol.id && e.type === "AFFECTED_BY"
  ).map((e) => GRAPH_NODES.find((n) => n.id === e.to));

  for (const inc of ownIncidents) {
    if (!inc) continue;
    findings.push({
      id: `R3_OWN_INCIDENT_${inc.id}`,
      rule: "R3",
      severity: "high",
      message: `${protocol.name} suffered a historical incident: '${inc.name}' with estimated loss of $${((inc.amountUsd || 0) / 1000000).toFixed(1)}M.`,
      path: [protocol.id, inc.id],
      subject: protocol.id,
      action: "warn",
      evidence: [{ source_url: inc.sourceUrl, title: inc.name }],
      details: { tags: ["incident_history"] },
    });
    addTag("incident_history");
  }

  for (const [depId, pathRec] of bestDepMap.entries()) {
    const depIncidents = GRAPH_EDGES.filter(
      (e) => e.from === depId && e.type === "AFFECTED_BY"
    ).map((e) => GRAPH_NODES.find((n) => n.id === e.to));

    for (const inc of depIncidents) {
      if (!inc) continue;
      findings.push({
        id: `R3_DEP_INCIDENT_${inc.id}`,
        rule: "R3",
        severity: "high",
        message: `${protocol.name} depends on '${depId}' via (${pathRec.nodes.join(" > ")}), which experienced historical exploit: '${inc.name}' ($${((inc.amountUsd || 0) / 1000000).toFixed(1)}M).`,
        path: pathRec.nodes,
        subject: depId,
        action: "cap",
        cap_usd: capital * 0.1 * mult,
        evidence: [{ source_url: inc.sourceUrl, title: inc.name }],
        details: { tags: ["dependency_incident"] },
      });
      addTag("dependency_incident");
    }
  }

  // --- RULE R4: Stablecoin & Peg Deviation ---
  for (const [depId, pathRec] of bestDepMap.entries()) {
    const targetNode = GRAPH_NODES.find((n) => n.id === depId);
    if (targetNode?.label === "Stablecoin") {
      const devPct = targetNode.pegDevPct || 0;
      if (Math.abs(devPct) > 1.5) {
        findings.push({
          id: `R4_PEG_DEVIATION_${depId}`,
          rule: "R4",
          severity: "high",
          message: `${targetNode.name} (${depId}) trades ${Math.abs(devPct).toFixed(2)}% off peg ($${targetNode.price?.toFixed(3)}). High risk of liquidation cascade.`,
          path: pathRec.nodes,
          subject: depId,
          action: "block",
          cap_usd: 0,
          evidence: pathRec.evidence,
          details: { tags: ["depegged_stablecoin"], deviation_pct: devPct },
        });
        addTag("depegged_stablecoin");
      } else if (
        targetNode.pegMechanism?.includes("algo") ||
        targetNode.pegMechanism?.includes("seigniorage")
      ) {
        findings.push({
          id: `R4_ALGO_PEG_${depId}`,
          rule: "R4",
          severity: "medium",
          message: `${protocol.name} depends on '${targetNode.name}', an uncollateralized algorithmic stablecoin mechanism.`,
          path: pathRec.nodes,
          subject: depId,
          action: "cap",
          cap_usd: capital * 0.05 * mult,
          evidence: pathRec.evidence,
          details: { tags: ["algorithmic_stablecoin"] },
        });
        addTag("algorithmic_stablecoin");
      }
    }
  }

  // --- RULE R5: Controller Weakness & Oracle Topology ---
  for (const [depId, pathRec] of bestDepMap.entries()) {
    const targetNode = GRAPH_NODES.find((n) => n.id === depId);
    if (targetNode?.label === "Controller") {
      if (
        targetNode.controllerType === "eoa" ||
        (targetNode.threshold !== undefined && targetNode.threshold <= 1)
      ) {
        findings.push({
          id: `R5_ADMIN_EOA_${depId}`,
          rule: "R5",
          severity: "high",
          message: `${protocol.name} is governed by a single-key externally owned account (${targetNode.name}). Privately held key can execute arbitrary upgrades.`,
          path: pathRec.nodes,
          subject: depId,
          action: "cap",
          cap_usd: capital * 0.05 * mult,
          evidence: pathRec.evidence,
          details: { tags: ["admin_eoa"] },
        });
        addTag("admin_eoa");
      } else if (
        targetNode.threshold !== undefined &&
        targetNode.threshold < 3
      ) {
        findings.push({
          id: `R5_WEAK_MULTISIG_${depId}`,
          rule: "R5",
          severity: "medium",
          message: `${targetNode.name} requires only ${targetNode.threshold} signers (< 3-signer threshold policy).`,
          path: pathRec.nodes,
          subject: depId,
          action: "cap",
          cap_usd: capital * 0.1 * mult,
          evidence: pathRec.evidence,
          details: { tags: ["weak_multisig"] },
        });
        addTag("weak_multisig");
      }

      if (targetNode.timelockHours !== undefined && targetNode.timelockHours <= 0) {
        findings.push({
          id: `R5_NO_TIMELOCK_${depId}`,
          rule: "R5",
          severity: "low",
          message: `${targetNode.name} has zero timelock delay (timelock: 0h). Upgrade transactions take immediate effect without notice window.`,
          path: pathRec.nodes,
          subject: depId,
          action: "warn",
          evidence: pathRec.evidence,
          details: { tags: ["no_timelock"] },
        });
        addTag("no_timelock");
      }
    }
  }

  // Single oracle detection
  const oraclePaths = Array.from(bestDepMap.values()).filter(
    (p) =>
      p.hops === 1 &&
      GRAPH_NODES.find((n) => n.id === p.target)?.label === "Oracle"
  );
  if (oraclePaths.length === 1) {
    const o = oraclePaths[0];
    const oNode = GRAPH_NODES.find((n) => n.id === o.target);
    findings.push({
      id: "R5_SINGLE_ORACLE",
      rule: "R5",
      severity: "low",
      message: `${protocol.name} relies on a single modelled oracle feed (${oNode?.name || o.target}). No secondary price feed redundancy detected.`,
      path: o.nodes,
      subject: o.target,
      action: "warn",
      evidence: o.evidence,
      details: { tags: ["single_oracle"] },
    });
    addTag("single_oracle");
  }

  // --- RULE R6: Market Signals & Yield Decomposition ---
  if (protocol.change_7d !== undefined && protocol.change_7d <= -30.0) {
    findings.push({
      id: "R6_TVL_DROP",
      rule: "R6",
      severity: "medium",
      message: `${protocol.name} TVL contracted ${Math.abs(protocol.change_7d).toFixed(1)}% over the trailing 7 days. Accelerated liquidity flight detected.`,
      path: [protocol.id],
      subject: protocol.id,
      action: "warn",
      details: { tags: ["tvl_drop"], change_7d: protocol.change_7d },
    });
    addTag("tvl_drop");
  }

  if (protocol.outlier) {
    findings.push({
      id: "R6_APY_OUTLIER",
      rule: "R6",
      severity: "low",
      message: `${protocol.name} liquidity pools exhibit anomalous APY metrics (${protocol.apy}% APY with ${protocol.apyReward}% in token rewards).`,
      path: [protocol.id],
      subject: protocol.id,
      action: "warn",
      details: { tags: ["reward_driven_yield"] },
    });
    addTag("reward_driven_yield");
  }

  // --- RULE R8: User Preferences ---
  const prefs = userProfile.preferences;
  if (prefs.max_position_pct) {
    const maxAllowedUsd = (capital * prefs.max_position_pct) / 100.0;
    const existingAmount =
      existingHoldings.find((p) => p.protocol_id === protocol.id)?.amount_usd || 0;
    if (existingAmount + proposal.amount_usd > maxAllowedUsd) {
      const room = Math.max(0, maxAllowedUsd - existingAmount);
      findings.push({
        id: "R8_MAX_POSITION",
        rule: "R8",
        severity: "medium",
        message: `Allocation exceeds user preference: max position size is ${prefs.max_position_pct}% of capital ($${maxAllowedUsd.toLocaleString()}).`,
        path: [protocol.id],
        subject: protocol.id,
        action: "cap",
        cap_usd: room,
        details: { tags: ["user_preference_cap"] },
      });
      addTag("user_preference_cap");
    }
  }

  if (
    protocol.category &&
    prefs.avoid_categories.map((c) => c.toLowerCase()).includes(protocol.category.toLowerCase())
  ) {
    findings.push({
      id: "R8_AVOID_CATEGORY",
      rule: "R8",
      severity: "high",
      message: `User preference active: forbid allocations to '${protocol.category}' protocols.`,
      path: [protocol.id],
      subject: protocol.id,
      action: "block",
      cap_usd: 0,
      details: { tags: ["user_avoid_category"] },
    });
    addTag("user_avoid_category");
  }

  // --- RULE R7: Learned Memory Rules & Mistake Repetition ---
  const activeTags = Array.from(tagsSet);
  for (const rule of userProfile.memory_rules) {
    if (activeTags.includes(rule.tag)) {
      const act = rule.action;
      const capUsd =
        rule.cap_pct !== undefined ? (capital * rule.cap_pct) / 100.0 : undefined;
      findings.push({
        id: `R7_MEM_RULE_${rule.id}`,
        rule: "R7",
        severity: act === "block" ? "high" : "medium",
        message: `Enforcing your learned memory rule #${rule.id}: ${rule.note}`,
        path: [protocol.id],
        subject: protocol.id,
        action: act,
        cap_usd: capUsd,
        memory_ref: { kind: "rule", id: rule.id, tag: rule.tag },
        details: { tags: ["learned_memory_rule"] },
      });
      addTag("learned_memory_rule");
    }
  }

  for (const mistake of userProfile.mistakes) {
    if (activeTags.includes(mistake.tag)) {
      findings.push({
        id: `R7_MISTAKE_${mistake.id}`,
        rule: "R7",
        severity: "medium",
        message: `Historical Loss Immunity: You lost $${mistake.loss_usd.toLocaleString()} on this pattern before (${mistake.summary}).`,
        path: [protocol.id],
        subject: protocol.id,
        action: "warn",
        memory_ref: { kind: "mistake", id: mistake.id, tag: mistake.tag },
        details: { tags: ["past_mistake_repetition"] },
      });
      addTag("past_mistake_repetition");
    }
  }

  // --- RULE S1: Synthetic Shock Contagion Loss ---
  for (const shock of syntheticShocks) {
    if (shock.node === protocol.id) {
      const loss = proposal.amount_usd * shock.severity;
      findings.push({
        id: "S1_DIRECT_SHOCK",
        rule: "S1",
        severity: "medium",
        message: `Contagion scenario: Target node '${protocol.name}' simulated failure at severity ${(shock.severity * 100).toFixed(0)}%. Estimated direct loss: $${loss.toLocaleString()}.`,
        path: [protocol.id],
        subject: protocol.id,
        action: shock.severity >= 0.25 ? "cap" : "warn",
        cap_usd: capital * 0.05,
        details: { estimated_loss_usd: loss, severity: shock.severity },
      });
    } else if (bestDepMap.has(shock.node)) {
      const p = bestDepMap.get(shock.node)!;
      const frac = shock.severity * p.strength;
      const loss = proposal.amount_usd * frac;
      findings.push({
        id: `S1_TRANSITIVE_SHOCK_${shock.node}`,
        rule: "S1",
        severity: "medium",
        message: `Contagion scenario: Upstream dependency '${shock.node}' fails at ${(shock.severity * 100).toFixed(0)}%. Estimated transitive loss across path (${p.nodes.join(" > ")}): $${loss.toLocaleString()}.`,
        path: p.nodes,
        subject: shock.node,
        action: frac >= 0.25 ? "cap" : "warn",
        cap_usd: capital * 0.05,
        details: { estimated_loss_usd: loss, contagion_fraction: frac },
      });
    }
  }

  // Sort findings by severity (high -> medium -> low -> info)
  const severityOrder = { high: 0, medium: 1, low: 2, info: 3 };
  findings.sort((a, b) => severityOrder[a.severity] - severityOrder[b.severity]);

  // Aggregate Verdict
  const isBlocked = findings.some((f) => f.action === "block");
  const caps = findings
    .filter((f) => f.action === "cap" && f.cap_usd !== undefined && f.cap_usd !== null)
    .map((f) => f.cap_usd as number);

  let allowedAmount = proposal.amount_usd;
  if (isBlocked) {
    allowedAmount = 0.0;
  } else if (caps.length > 0) {
    allowedAmount = Math.min(proposal.amount_usd, ...caps);
  }

  let outcome: "ALLOW" | "ALLOW_WITH_CAP" | "WARN" | "BLOCK" = "ALLOW";
  if (isBlocked) {
    outcome = "BLOCK";
  } else if (allowedAmount < proposal.amount_usd) {
    outcome = allowedAmount > 0 ? "ALLOW_WITH_CAP" : "BLOCK";
  } else if (findings.some((f) => f.action === "warn")) {
    outcome = "WARN";
  }

  const gaps: string[] = [];
  if (depPaths.length === 0) gaps.push("no verified dependencies modelled");
  if (protocol.audits === null || protocol.audits === undefined)
    gaps.push("audit record unverified");
  if (protocol.age_days === undefined) gaps.push("listing age unverified");

  return {
    outcome,
    proposal,
    allowed_amount_usd: Number(allowedAmount.toFixed(2)),
    findings,
    tags: Array.from(tagsSet),
    coverage: {
      modelled: true,
      dependency_paths: depPaths.length,
      max_hops: 3,
      gaps,
    },
    rules_version: "2024.10-falkordb-deterministic",
    disclaimer:
      "Deterministic policy evaluation. Unmodelled entities fail-closed. Not financial advice.",
  };
}

// Issue cryptographic HMAC Gate Token for permissible verdicts
export function issueGateToken(verdict: Verdict): GateToken | null {
  if (verdict.outcome === "BLOCK" || verdict.allowed_amount_usd <= 0) {
    return null;
  }

  const now = 1729240000000;
  const expiresAt = now + 15 * 60 * 1000; // 15 minute validity
  const payloadStr = `${verdict.proposal.protocol_id}:${verdict.allowed_amount_usd}:${now}`;

  // Simple deterministic client HMAC representation for demo
  let hash = 0;
  for (let i = 0; i < payloadStr.length; i++) {
    hash = (hash << 5) - hash + payloadStr.charCodeAt(i);
    hash |= 0;
  }
  const hmacSig = `hmac_sha256_${Math.abs(hash).toString(16).padStart(8, "0")}`;

  return {
    token: `gatetoken_${Math.abs(hash).toString(36)}_${hmacSig}`,
    issued_at: now,
    expires_at: expiresAt,
    proposal_hash: payloadStr,
    allowed_amount_usd: verdict.allowed_amount_usd,
    hmac_signature: hmacSig,
  };
}
