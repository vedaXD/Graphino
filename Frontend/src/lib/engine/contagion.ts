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
  // Edge: (Protocol)-[:USES_ORACLE | :DEPENDS_ON | :GOVERNED_BY]->(Dependency)
  // Incoming: e.to === shockNodeId, e.from is the dependent
  interface QueueItem {
    nodeId: string;
    hops: number;
    path: string[];
    strength: number;
  }

  const queue: QueueItem[] = [
    {
      nodeId: shockNodeId,
      hops: 0,
      path: [shockNodeId],
      strength: 1.0,
    },
  ];

  while (queue.length > 0) {
    const current = queue.shift()!;
    if (current.hops >= maxHops) continue;

    // Find all nodes that depend on current.nodeId
    const incomingEdges = GRAPH_EDGES.filter(
      (e) =>
        e.to === current.nodeId &&
        e.verified &&
        e.risk_eligible &&
        !e.is_test
    );

    for (const edge of incomingEdges) {
      const dependentId = edge.from;
      const dependentNode = GRAPH_NODES.find((n) => n.id === dependentId);
      if (!dependentNode) continue;

      const newHop = current.hops + 1;
      const newPath = [dependentId, ...current.path];
      const newStrength = current.strength * (edge.strength || 1.0);
      const contagionFrac = Math.min(1.0, severity * newStrength);

      const pathKey = `${dependentId}_${newHop}`;
      if (!visited.has(pathKey)) {
        visited.add(pathKey);

        const holding = positions.find((p) => p.protocol_id === dependentId);
        const allocatedUsd = holding ? holding.amount_usd : 0;
        const lossUsd = allocatedUsd * contagionFrac;

        impactedProtocols.push({
          protocol_id: dependentId,
          name: dependentNode.name,
          hops: newHop,
          path: newPath,
          path_strength: Number(newStrength.toFixed(3)),
          contagion_fraction: Number(contagionFrac.toFixed(3)),
          estimated_position_loss_usd: Number(lossUsd.toFixed(2)),
          allocated_usd: allocatedUsd,
        });

        queue.push({
          nodeId: dependentId,
          hops: newHop,
          path: newPath,
          strength: newStrength,
        });
      }
    }
  }

  // Sort by highest contagion fraction
  impactedProtocols.sort((a, b) => b.contagion_fraction - a.contagion_fraction);

  const totalPortfolioCapital = positions.reduce((sum, p) => sum + p.amount_usd, 0);
  const totalLossUsd = impactedProtocols.reduce(
    (sum, p) => sum + p.estimated_position_loss_usd,
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
  };
}

// Compute Systemic Importance Leaderboard (PageRank & Transitive Dependents)
export function computeSystemicImportance(): SystemicRankItem[] {
  const eligibleEdges = GRAPH_EDGES.filter(
    (e) => e.verified && e.risk_eligible && !e.is_test
  );

  const items: SystemicRankItem[] = [];

  for (const node of GRAPH_NODES) {
    // 1. Direct dependents: protocols with direct outgoing edge to this node
    const directDependents = eligibleEdges
      .filter((e) => e.to === node.id)
      .map((e) => e.from);

    // 2. Transitive dependents (walk backwards up to 3 hops)
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

    // 3. Approximate PageRank Score based on inbound edge weight and centralities
    let pageRank = 0.05;
    for (const edge of eligibleEdges.filter((e) => e.to === node.id)) {
      const sourceNode = GRAPH_NODES.find((n) => n.id === edge.from);
      const tvlWeight = sourceNode?.tvl_usd ? Math.log10(sourceNode.tvl_usd) / 10 : 0.5;
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
