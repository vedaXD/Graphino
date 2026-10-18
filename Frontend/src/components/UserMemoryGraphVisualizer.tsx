"use client";

import React, { useState, useMemo } from "react";
import { UserProfile, PortfolioPosition, MemoryRule, MistakeRecord } from "@/lib/types";

interface UserMemoryGraphVisualizerProps {
  currentProfile: UserProfile;
  onAuditProtocol?: (protocolId: string) => void;
}

interface MemoryNode {
  id: string;
  label: "User" | "Position" | "Rule" | "Episode" | "Preference" | "Mistake";
  name: string;
  subtext?: string;
  status?: string;
  amountUsd?: number;
  x: number;
  y: number;
  isRecent?: boolean;
}

interface MemoryEdge {
  id: string;
  from: string;
  to: string;
  type: "OWNS_POSITION" | "LEARNED_RULE" | "HAD_EPISODE" | "HAS_PREFERENCE" | "RECORDED_MISTAKE";
}

export const UserMemoryGraphVisualizer: React.FC<UserMemoryGraphVisualizerProps> = ({
  currentProfile,
  onAuditProtocol,
}) => {
  const [selectedNodeId, setSelectedNodeId] = useState<string>(currentProfile.user_id);
  const [filterType, setFilterType] = useState<string>("All");
  const [zoomLevel, setZoomLevel] = useState<number>(1);

  // Compute 2D coordinates for the user memory graph
  const { nodes, edges } = useMemo(() => {
    const center = { x: 360, y: 220 };
    const nodeList: MemoryNode[] = [];
    const edgeList: MemoryEdge[] = [];

    // Central User Node
    const userNode: MemoryNode = {
      id: currentProfile.user_id,
      label: "User",
      name: currentProfile.display_name || currentProfile.user_id,
      subtext: `Risk: ${(currentProfile.preferences?.risk_tolerance || "balanced").toUpperCase()}`,
      x: center.x,
      y: center.y,
    };
    nodeList.push(userNode);

    // Positions (placed in upper right arc)
    const positions = currentProfile.positions || [];
    positions.forEach((pos, idx) => {
      const angle = -Math.PI / 4 + (idx / Math.max(1, positions.length)) * (Math.PI / 2);
      const radius = 150 + (idx % 2) * 35;
      const nodeId = `pos-${pos.protocol_id}-${idx}`;
      nodeList.push({
        id: nodeId,
        label: "Position",
        name: pos.name || pos.protocol_id,
        subtext: `$${pos.amount_usd.toLocaleString()} · OPEN`,
        amountUsd: pos.amount_usd,
        status: "OPEN",
        x: Math.round(center.x + Math.cos(angle) * radius),
        y: Math.round(center.y + Math.sin(angle) * radius),
        isRecent: idx === 0,
      });
      edgeList.push({
        id: `e-user-pos-${idx}`,
        from: currentProfile.user_id,
        to: nodeId,
        type: "OWNS_POSITION",
      });
    });

    // Learned Rules (placed in lower left arc)
    const rules = currentProfile.memory_rules || [];
    rules.forEach((rule, idx) => {
      const angle = (3 * Math.PI) / 4 + (idx / Math.max(1, rules.length)) * (Math.PI / 2);
      const radius = 145 + (idx % 2) * 30;
      const nodeId = `rule-${rule.id}`;
      nodeList.push({
        id: nodeId,
        label: "Rule",
        name: rule.tag || rule.id,
        subtext: rule.action.toUpperCase(),
        x: Math.round(center.x + Math.cos(angle) * radius),
        y: Math.round(center.y + Math.sin(angle) * radius),
      });
      edgeList.push({
        id: `e-user-rule-${idx}`,
        from: currentProfile.user_id,
        to: nodeId,
        type: "LEARNED_RULE",
      });
    });

    // Preferences Node (placed top center)
    const prefNodeId = `pref-${currentProfile.user_id}`;
    nodeList.push({
      id: prefNodeId,
      label: "Preference",
      name: "Risk Preferences",
      subtext: `Tolerance: ${(currentProfile.preferences?.risk_tolerance || "balanced").toUpperCase()}`,
      x: center.x,
      y: center.y - 140,
    });
    edgeList.push({
      id: `e-user-pref`,
      from: currentProfile.user_id,
      to: prefNodeId,
      type: "HAS_PREFERENCE",
    });

    // Past Mistakes (placed lower right)
    const mistakes = currentProfile.mistakes || [];
    mistakes.forEach((m, idx) => {
      const angle = Math.PI / 4 + (idx / Math.max(1, mistakes.length)) * (Math.PI / 3);
      const radius = 160;
      const nodeId = `mistake-${m.id}`;
      nodeList.push({
        id: nodeId,
        label: "Mistake",
        name: m.protocol_involved,
        subtext: `-$${m.loss_usd.toLocaleString()}`,
        amountUsd: m.loss_usd,
        x: Math.round(center.x + Math.cos(angle) * radius),
        y: Math.round(center.y + Math.sin(angle) * radius),
      });
      edgeList.push({
        id: `e-user-mistake-${idx}`,
        from: currentProfile.user_id,
        to: nodeId,
        type: "RECORDED_MISTAKE",
      });
    });

    // Recent Execution Episode (placed lower center)
    if (positions.length > 0) {
      const epNodeId = `ep-latest`;
      nodeList.push({
        id: epNodeId,
        label: "Episode",
        name: `Episode: ${positions[0].name}`,
        subtext: "Gated Allocation",
        x: center.x - 70,
        y: center.y + 140,
        isRecent: true,
      });
      edgeList.push({
        id: `e-user-ep`,
        from: currentProfile.user_id,
        to: epNodeId,
        type: "HAD_EPISODE",
      });
    }

    return { nodes: nodeList, edges: edgeList };
  }, [currentProfile]);

  const selectedNode = useMemo(() => {
    return nodes.find((n) => n.id === selectedNodeId) || nodes[0];
  }, [selectedNodeId, nodes]);

  const connectedEdges = useMemo(() => {
    return edges.filter((e) => e.from === selectedNode?.id || e.to === selectedNode?.id);
  }, [selectedNode, edges]);

  // Cypher representation
  const cypherQuery = useMemo(() => {
    if (selectedNode?.label === "Position") {
      return `// FalkorDB Tenant Memory Query\nMATCH (u:User {user_id: '${currentProfile.user_id}'})-[r:OWNS_POSITION]->(p:Position)\nWHERE p.protocol_id = '${selectedNode.name}'\nRETURN u, r, p;`;
    }
    if (selectedNode?.label === "Rule") {
      return `// FalkorDB Learned Procedural Rule\nMATCH (u:User {user_id: '${currentProfile.user_id}'})-[r:LEARNED_RULE]->(rule:Rule)\nRETURN rule.tag, rule.action, rule.note;`;
    }
    return `// FalkorDB Full Tenant Memory Graph (mem_${currentProfile.user_id})\nMATCH (u:User {user_id: '${currentProfile.user_id}'})-[r]->(target)\nRETURN u, type(r), target;`;
  }, [selectedNode, currentProfile]);

  return (
    <div className="bg-[#ffffff] border border-[#d8d4d4] rounded-[4px] p-5 space-y-4 shadow-xs">
      {/* Header and Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#d8d4d4] pb-3">
        <div>
          <div className="flex items-center gap-2">
            <span className="text-[12px] font-mono font-bold uppercase tracking-wider text-[#181011]">
              Live Tenant Memory Graph
            </span>
            <span className="text-[10px] font-mono bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded">
              mem_{currentProfile.user_id}
            </span>
          </div>
          <div className="text-[11px] font-mono text-[#666666] mt-0.5">
            Isolated tenant graph in FalkorDB: {currentProfile.positions.length} active positions · {currentProfile.memory_rules.length} rules · {currentProfile.mistakes.length} mistakes
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setZoomLevel((z) => Math.max(0.7, z - 0.15))}
            className="w-7 h-7 flex items-center justify-center font-mono text-xs border border-[#d8d4d4] rounded bg-[#ffffff] hover:bg-[#f3f1ed]"
          >
            -
          </button>
          <span className="font-mono text-[11px] text-[#666666] w-12 text-center">
            {Math.round(zoomLevel * 100)}%
          </span>
          <button
            onClick={() => setZoomLevel((z) => Math.min(1.4, z + 0.15))}
            className="w-7 h-7 flex items-center justify-center font-mono text-xs border border-[#d8d4d4] rounded bg-[#ffffff] hover:bg-[#f3f1ed]"
          >
            +
          </button>
          <button
            onClick={() => setZoomLevel(1)}
            className="text-[10px] font-mono px-2 py-1 border border-[#d8d4d4] rounded bg-[#ffffff] hover:bg-[#f3f1ed] text-[#666666]"
          >
            Reset
          </button>
        </div>
      </div>

      {/* SVG Canvas and Inspector Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start">
        {/* Left: Interactive SVG Memory Canvas (7 cols) */}
        <div className="lg:col-span-8 border border-[#d8d4d4] rounded bg-[#faf9f8] relative overflow-hidden h-[440px]">
          <svg
            className="w-full h-full cursor-grab"
            viewBox="0 0 720 440"
            style={{
              transform: `scale(${zoomLevel})`,
              transformOrigin: "center center",
              transition: "transform 0.2s ease-out",
            }}
          >
            <defs>
              <marker
                id="mem-arrow-default"
                viewBox="0 0 10 10"
                refX="18"
                refY="5"
                markerWidth="6"
                markerHeight="6"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#888888" />
              </marker>
              <marker
                id="mem-arrow-active"
                viewBox="0 0 10 10"
                refX="20"
                refY="5"
                markerWidth="7"
                markerHeight="7"
                orient="auto-start-reverse"
              >
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#181011" />
              </marker>
            </defs>

            {/* Edge Lines */}
            {edges.map((edge) => {
              const src = nodes.find((n) => n.id === edge.from);
              const tgt = nodes.find((n) => n.id === edge.to);
              if (!src || !tgt) return null;

              const isConnected =
                edge.from === selectedNode?.id || edge.to === selectedNode?.id;

              const midX = (src.x + tgt.x) / 2;
              const midY = (src.y + tgt.y) / 2;

              return (
                <g key={edge.id}>
                  <line
                    x1={src.x}
                    y1={src.y}
                    x2={tgt.x}
                    y2={tgt.y}
                    stroke={isConnected ? "#181011" : "#cccccc"}
                    strokeWidth={isConnected ? 2 : 1.2}
                    strokeDasharray={edge.type === "LEARNED_RULE" ? "3,3" : undefined}
                    markerEnd={isConnected ? "url(#mem-arrow-active)" : "url(#mem-arrow-default)"}
                  />
                  {isConnected && (
                    <text
                      x={midX}
                      y={midY - 4}
                      textAnchor="middle"
                      className="text-[9px] font-mono fill-[#666666] font-bold bg-white"
                    >
                      {edge.type}
                    </text>
                  )}
                </g>
              );
            })}

            {/* Nodes */}
            {nodes.map((node) => {
              const isSelected = node.id === selectedNode?.id;
              let fill = "#ffffff";
              let stroke = "#d8d4d4";
              let badgeColor = "#666666";

              if (node.label === "User") {
                fill = "#181011";
                stroke = "#181011";
                badgeColor = "#ffffff";
              } else if (node.label === "Position") {
                fill = "#ecfdf5";
                stroke = "#10b981";
                badgeColor = "#047857";
              } else if (node.label === "Rule") {
                fill = "#f3e8ff";
                stroke = "#a855f7";
                badgeColor = "#7e22ce";
              } else if (node.label === "Episode") {
                fill = "#eff6ff";
                stroke = "#3b82f6";
                badgeColor = "#1d4ed8";
              } else if (node.label === "Mistake") {
                fill = "#fef2f2";
                stroke = "#ef4444";
                badgeColor = "#b91c1c";
              } else if (node.label === "Preference") {
                fill = "#fef3c7";
                stroke = "#f59e0b";
                badgeColor = "#b45309";
              }

              const radius = node.label === "User" ? 28 : 22;

              return (
                <g
                  key={node.id}
                  transform={`translate(${node.x}, ${node.y})`}
                  className="cursor-pointer"
                  onClick={() => setSelectedNodeId(node.id)}
                >
                  {/* Glowing ring for recently updated position or episode */}
                  {node.isRecent && (
                    <circle
                      r={radius + 7}
                      fill="none"
                      stroke="#10b981"
                      strokeWidth="2"
                      strokeDasharray="4,4"
                      className="animate-spin"
                      style={{ transformOrigin: "0 0" }}
                    />
                  )}

                  {/* Node Circle */}
                  <circle
                    r={radius}
                    fill={fill}
                    stroke={isSelected ? "#181011" : stroke}
                    strokeWidth={isSelected ? 2.5 : 1.5}
                  />

                  {/* Text */}
                  <text
                    textAnchor="middle"
                    y={4}
                    className={`text-[10px] font-mono font-bold pointer-events-none ${
                      node.label === "User" ? "fill-[#ffffff]" : "fill-[#181011]"
                    }`}
                  >
                    {node.name.length > 9 ? node.name.slice(0, 8) + "…" : node.name}
                  </text>

                  {/* Label under node */}
                  <text
                    textAnchor="middle"
                    y={radius + 12}
                    className="text-[9px] font-mono fill-[#666666] pointer-events-none"
                  >
                    {node.label}
                  </text>
                </g>
              );
            })}
          </svg>

          {/* Legend */}
          <div className="absolute bottom-3 left-3 bg-[#ffffff]/90 backdrop-blur-xs border border-[#d8d4d4] rounded p-2 flex flex-wrap items-center gap-2 text-[10px] font-mono">
            <span className="text-[#888888]">MEM_GRAPH:</span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-black"></span> User
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Position
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-purple-500"></span> Rule
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-blue-500"></span> Episode
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-red-500"></span> Mistake
            </span>
          </div>
        </div>

        {/* Right: Selected Node Details & Live Cypher (4 cols) */}
        <div className="lg:col-span-4 space-y-4">
          <div className="border border-[#d8d4d4] rounded bg-[#faf9f8] p-4 space-y-3 text-[11px] font-mono">
            <div className="flex items-center justify-between border-b border-[#d8d4d4] pb-2">
              <span className="text-[10px] uppercase font-bold text-[#888888]">
                {selectedNode?.label} Details
              </span>
              {selectedNode?.isRecent && (
                <span className="text-[9px] bg-emerald-100 text-emerald-800 px-1.5 py-0.5 rounded font-bold">
                  UPDATED LIVE
                </span>
              )}
            </div>

            <div className="space-y-1.5">
              <div className="font-bold text-[14px] text-[#181011]">
                {selectedNode?.name}
              </div>
              <div className="text-[#666666]">
                {selectedNode?.subtext}
              </div>
              {selectedNode?.amountUsd !== undefined && (
                <div className="text-emerald-700 font-bold">
                  ${selectedNode.amountUsd.toLocaleString()} USD
                </div>
              )}
            </div>

            {/* Connected Relationships */}
            <div className="space-y-1 pt-2 border-t border-[#e5e5e5]">
              <span className="text-[10px] uppercase font-bold text-[#888888] block">
                Connected Edges ({connectedEdges.length})
              </span>
              <div className="space-y-1 max-h-28 overflow-y-auto">
                {connectedEdges.map((e) => (
                  <div key={e.id} className="p-1 bg-[#ffffff] border border-[#e5e5e5] rounded text-[10px] flex justify-between">
                    <span>{e.type}</span>
                    <span className="text-[#888888]">{e.to}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Live Cypher Terminal */}
          <div className="bg-[#181011] text-[#f3f1ed] border border-[#302023] rounded p-3 space-y-1.5 font-mono">
            <div className="flex items-center justify-between text-[10px] text-[#aaaaaa] border-b border-[#302023] pb-1.5">
              <span>CYPHER MEMORY RUNNER</span>
              <span className="text-emerald-400">PORT 6379</span>
            </div>
            <pre className="text-[10px] text-emerald-400 overflow-x-auto p-1.5 bg-[#0c0808] rounded border border-[#302023] leading-relaxed">
              {cypherQuery}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
};
