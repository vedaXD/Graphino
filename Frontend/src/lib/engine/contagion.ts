import { GRAPH_NODES, GRAPH_EDGES } from "../data/graphData";
import { ShockSimulationResult, SystemicRankItem, PortfolioPosition } from "../types";

// Simulate failure contagion walking incoming dependency edges backwards
export function simulateShock(
  shockNodeId: string,
  severity: number = 1.0,
  maxHops: number = 3,
  positions: PortfolioPosition[] = []
): ShockSimulationResult {
  const targetNode = GRAPH_NODES.find((n) => n.id === shockNodeId);
  const impactedProtocols: ShockSimulationResult["impacted_protocols"] = [];
  const visited = new Set<string>();

  // Backward BFS: who depends on shockNodeId?
  // Edge: (Dependent)-[:USES_ORACLE | :DEPENDS_ON | :GOVERNED_BY | :DEPLOYED_ON | :ASSOCIATED_WITH_ASSET | :HAS_POOL]->(Dependency)
  // Incoming: e.to === shockNodeId, e.from is the dependent
  interface QueueItem {
    nodeId: string;
    hops: number;
    path: string[];
    strength: number;
  }

  const initialNodeName = targetNode?.name || shockNodeId;

  const queue: QueueItem[] = [
    {
      nodeId: shockNodeId,
      hops: 0,
      path: [initialNodeName],
      strength: 1.0,
    },
  ];

  while (queue.length > 0) {
    const current = queue.shift()!;
    if (current.hops >= maxHops) continue;

    // Find all nodes that depend on current.nodeId or current.nodeName
    const currentNode = GRAPH_NODES.find((n) => n.id === current.nodeId);
    const incomingEdges = GRAPH_EDGES.filter((e) => {
      if (e.is_test) return false;
      const matchesTo =
        e.to === current.nodeId ||
        (currentNode && e.to.toLowerCase() === currentNode.name.toLowerCase()) ||
        (currentNode && e.to.toLowerCase() === currentNode.id.toLowerCase());

      if (!matchesTo) return false;

      // Allow all real infrastructure & structural dependency relationships
      return (
        e.type === "USES_ORACLE" ||
        e.type === "DEPENDS_ON" ||
        e.type === "GOVERNED_BY" ||
        e.type === "DEPLOYED_ON" ||
        e.type === "ASSOCIATED_WITH_ASSET" ||
        e.type === "HAS_POOL" ||
        e.verified ||
        e.risk_eligible
      );
    });

    for (const edge of incomingEdges) {
      const dependentId = edge.from;
      const dependentNode = GRAPH_NODES.find(
        (n) => n.id === dependentId || n.name.toLowerCase() === dependentId.toLowerCase()
      );
      if (!dependentNode) continue;

      const newHop = current.hops + 1;
      const newPath = [dependentNode.name, ...current.path];
      const newStrength = current.strength * (edge.strength || 0.8);
      const contagionFrac = Math.min(1.0, severity * newStrength);

      const pathKey = `${dependentNode.id}_${newHop}`;
      if (!visited.has(pathKey)) {
        visited.add(pathKey);

        const holding = positions.find(
          (p) =>
            p.protocol_id === dependentNode.id ||
            p.protocol_id.toLowerCase() === dependentNode.id.toLowerCase() ||
            p.name.toLowerCase() === dependentNode.name.toLowerCase()
        );
        const allocatedUsd = holding ? holding.amount_usd : 0;
        const lossUsd = allocatedUsd * contagionFrac;

        impactedProtocols.push({
          protocol_id: dependentNode.id,
          name: dependentNode.name,
          hops: newHop,
          path: newPath,
          path_strength: Number(newStrength.toFixed(3)),
          contagion_fraction: Number(contagionFrac.toFixed(3)),
          estimated_position_loss_usd: Number(lossUsd.toFixed(2)),
          allocated_usd: allocatedUsd,
          tvl_usd: dependentNode.tvl_usd,
        });

        queue.push({
          nodeId: dependentNode.id,
          hops: newHop,
          path: newPath,
          strength: newStrength,
        });
      }
    }
  }

  // Sort by highest portfolio loss, then highest contagion fraction
  impactedProtocols.sort(
    (a, b) =>
      b.estimated_position_loss_usd - a.estimated_position_loss_usd ||
      b.contagion_fraction - a.contagion_fraction
  );

  const totalPortfolioCapital = positions.reduce((sum, p) => sum + p.amount_usd, 0);
  const totalLossUsd = impactedProtocols.reduce(
    (sum, p) => sum + p.estimated_position_loss_usd,
    0
  );
  const totalTvlAtRisk = impactedProtocols.reduce(
    (sum, p) => sum + (p.tvl_usd || 0),
    0
  );
  const lossPct =
    totalPortfolioCapital > 0 ? (totalLossUsd / totalPortfolioCapital) * 100.0 : 0;

  return {
    shock_node: targetNode?.name || shockNodeId,
    severity,
    max_hops: maxHops,
    impacted_protocols: impactedProtocols,
    total_portfolio_loss_usd: Number(totalLossUsd.toFixed(2)),
    portfolio_at_risk_pct: Number(lossPct.toFixed(1)),
    total_systemic_tvl_at_risk_usd: totalTvlAtRisk,
  };
}

// Compute Systemic Importance Leaderboard (PageRank & Transitive Dependents)
export function computeSystemicImportance(): SystemicRankItem[] {
  const eligibleEdges = GRAPH_EDGES.filter(
    (e) =>
      !e.is_test &&
      (e.type === "USES_ORACLE" ||
        e.type === "DEPENDS_ON" ||
        e.type === "GOVERNED_BY" ||
        e.type === "DEPLOYED_ON" ||
        e.type === "ASSOCIATED_WITH_ASSET" ||
        e.type === "HAS_POOL" ||
        e.verified ||
        e.risk_eligible)
  );

  const items: SystemicRankItem[] = [];

  for (const node of GRAPH_NODES) {
    // Direct dependents: protocols/nodes with direct outgoing edge to this node
    const directDependents = eligibleEdges
      .filter(
        (e) =>
          e.to === node.id || e.to.toLowerCase() === node.name.toLowerCase()
      )
      .map((e) => e.from);

    // Filter out leaf protocols from leaderboard so it focuses on critical infrastructure
    if (directDependents.length === 0 && node.label === "Protocol") continue;

    // Transitive dependents (walk backwards up to 3 hops)
    const transitiveSet = new Set<string>();
    const queue = [...directDependents];
    queue.forEach((d) => transitiveSet.add(d));

    let depth = 0;
    while (queue.length > 0 && depth < 3) {
      depth++;
      const cur = queue.shift()!;
      const nextLevel = eligibleEdges
        .filter((e) => e.to === cur)
        .map((e) => e.from);
      for (const nl of nextLevel) {
        if (!transitiveSet.has(nl)) {
          transitiveSet.add(nl);
          queue.push(nl);
        }
      }
    }

    // PageRank score based on inbound edge weight and dependent TVLs
    let pageRank = 0.05;
    for (const edge of eligibleEdges.filter(
      (e) => e.to === node.id || e.to.toLowerCase() === node.name.toLowerCase()
    )) {
      const sourceNode = GRAPH_NODES.find((n) => n.id === edge.from);
      const tvlWeight = sourceNode?.tvl_usd
        ? Math.log10(sourceNode.tvl_usd) / 10
        : 0.5;
      pageRank += (edge.strength || 0.8) * tvlWeight * 0.15;
    }

    // Assign Tier
    let tier: SystemicRankItem["systemic_tier"] = "STANDARD";
    if (transitiveSet.size >= 4 || pageRank >= 0.5) {
      tier = "CRITICAL";
    } else if (transitiveSet.size >= 2 || pageRank >= 0.3) {
      tier = "HIGH";
    } else if (transitiveSet.size >= 1) {
      tier = "ELEVATED";
    }

    items.push({
      id: node.id,
      name: node.name,
      label: node.label,
      direct_dependents_count: directDependents.length,
      transitive_dependents_count: transitiveSet.size,
      pagerank_score: Number(pageRank.toFixed(3)),
      systemic_tier: tier,
    });
  }

  // Sort by highest pagerank score
  return items.sort((a, b) => b.pagerank_score - a.pagerank_score);
}
