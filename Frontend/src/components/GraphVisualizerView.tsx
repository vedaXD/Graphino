"use client";

import React, { useState, useMemo } from "react";
import { GRAPH_NODES, GRAPH_EDGES } from "@/lib/data/graphData";
import { EntityType, GraphNode, GraphEdge } from "@/lib/types";

interface GraphVisualizerViewProps {
  onAuditProtocol: (protocolId: string) => void;
  onSimulateShock: (nodeId: string) => void;
}

// Visual color schemes by entity type
const ENTITY_COLORS: Record<string, { bg: string; border: string; text: string; dot: string }> = {
  Protocol: { bg: "#eff6ff", border: "#3b82f6", text: "#1d4ed8", dot: "#2563eb" },
  Oracle: { bg: "#fef3c7", border: "#f59e0b", text: "#b45309", dot: "#d97706" },
  Controller: { bg: "#f3e8ff", border: "#a855f7", text: "#7e22ce", dot: "#9333ea" },
  Chain: { bg: "#ecfdf5", border: "#10b981", text: "#047857", dot: "#059669" },
  Stablecoin: { bg: "#f0fdfa", border: "#14b8a6", text: "#0f766e", dot: "#0d9488" },
  Incident: { bg: "#fef2f2", border: "#ef4444", text: "#b91c1c", dot: "#dc2626" },
  Pool: { bg: "#f8fafc", border: "#94a3b8", text: "#475569", dot: "#64748b" },
  Evidence: { bg: "#faf5ff", border: "#c084fc", text: "#6b21a8", dot: "#7e22ce" },
  Default: { bg: "#f3f4f6", border: "#9ca3af", text: "#374151", dot: "#4b5563" },
};

const CYPHER_PRESETS = [
  {
    title: "Aave V3 Dependencies",
    nodeId: "aave-v3",
    query: `MATCH (p:Protocol {id: 'aave-v3'})-[r:USES_ORACLE|DEPENDS_ON|GOVERNED_BY]->(target)\nRETURN p.display_name, type(r), target.display_name;`,
    description: "Evaluates oracles, controllers, and protocol dependencies for Aave V3.",
  },
  {
    title: "Chainlink Systemic Exposure",
    nodeId: "chainlink-price-feeds",
    query: `MATCH (o:Oracle {id: 'chainlink-price-feeds'})<-[r:USES_ORACLE]-(p:Protocol)\nRETURN p.name, p.tvl_usd\nORDER BY p.tvl_usd DESC;`,
    description: "Finds all protocols dependent on Chainlink price feed feeds.",
  },
  {
    title: "Governance Timelocks & Multisigs",
    nodeId: "aave-governance",
    query: `MATCH (c:Controller)<-[r:GOVERNED_BY]-(p:Protocol)\nRETURN p.name, c.controllerType, c.timelockHours, c.threshold;`,
    description: "Inspects decentralization risks and admin privileges across protocols.",
  },
  {
    title: "Incident Blast Radius",
    nodeId: "incident:euler-hack-2023",
    query: `MATCH (i:Incident)-[r:AFFECTED_BY|RELATED_TO]-(p:Protocol)\nRETURN i.name, i.amountUsd, p.name;`,
    description: "Traces contagion paths from known historical security exploits.",
  },
];

export const GraphVisualizerView: React.FC<GraphVisualizerViewProps> = ({
  onAuditProtocol,
  onSimulateShock,
}) => {
  const [selectedNodeId, setSelectedNodeId] = useState<string>("aave-v3");
  const [filterType, setFilterType] = useState<string>("All");
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [hoveredNodeId, setHoveredNodeId] = useState<string | null>(null);
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [viewMode, setViewMode] = useState<"focal" | "cluster">("focal");

  // Filter nodes for search and category
  const filteredNodes = useMemo(() => {
    return GRAPH_NODES.filter((n) => {
      const matchType = filterType === "All" || n.label === filterType;
      const matchQuery =
        searchQuery.trim() === "" ||
        n.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        n.id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        n.label.toLowerCase().includes(searchQuery.toLowerCase());
      return matchType && matchQuery;
    });
  }, [filterType, searchQuery]);

  const selectedNode = useMemo(() => {
    return (
      GRAPH_NODES.find((n) => n.id === selectedNodeId) ||
      filteredNodes[0] ||
      GRAPH_NODES[0]
    );
  }, [selectedNodeId, filteredNodes]);

  // Direct dependencies (outgoing) and dependents (incoming)
  const directOutgoingEdges = useMemo(() => {
    return GRAPH_EDGES.filter((e) => e.from === selectedNode?.id);
  }, [selectedNode]);

  const directIncomingEdges = useMemo(() => {
    return GRAPH_EDGES.filter((e) => e.to === selectedNode?.id);
  }, [selectedNode]);

  // Build focal subgraph: selected node at center, 1-hop connected nodes positioned around
  const focalGraph = useMemo(() => {
    if (!selectedNode) return { nodes: [], edges: [] };

    // Get all 1-hop connected node IDs
    const connectedNodeIds = new Set<string>();
    connectedNodeIds.add(selectedNode.id);

    directOutgoingEdges.forEach((e) => connectedNodeIds.add(e.to));
    directIncomingEdges.slice(0, 8).forEach((e) => connectedNodeIds.add(e.from));

    // Also include a few relevant high-importance nodes for context if graph is small
    if (connectedNodeIds.size < 6) {
      ["chainlink-price-feeds", "aave-governance", "ethereum", "morpho-blue"].forEach((id) => {
        if (GRAPH_NODES.some((n) => n.id === id)) connectedNodeIds.add(id);
      });
    }

    const focalNodesList = GRAPH_NODES.filter((n) => connectedNodeIds.has(n.id));

    // Compute 2D coordinates
    // Center: (360, 240)
    const centerX = 360;
    const centerY = 240;
    const radius = 170;

    const positionedNodes = focalNodesList.map((node) => {
      if (node.id === selectedNode.id) {
        return { ...node, x: centerX, y: centerY, isCenter: true };
      }
      // Place outgoing nodes on the right arc, incoming on the left arc
      const isOutgoing = directOutgoingEdges.some((e) => e.to === node.id);
      const isIncoming = directIncomingEdges.some((e) => e.from === node.id);

      const otherNodes = focalNodesList.filter((n) => n.id !== selectedNode.id);
      const idx = otherNodes.findIndex((n) => n.id === node.id);
      const total = otherNodes.length;

      let angle: number;
      if (isOutgoing && !isIncoming) {
        angle = -Math.PI / 3 + (idx / Math.max(1, total - 1)) * ((2 * Math.PI) / 3);
      } else if (isIncoming && !isOutgoing) {
        angle = (2 * Math.PI) / 3 + (idx / Math.max(1, total - 1)) * ((2 * Math.PI) / 3);
      } else {
        angle = (idx / Math.max(1, total)) * 2 * Math.PI;
      }

      return {
        ...node,
        x: Math.round(centerX + Math.cos(angle) * radius),
        y: Math.round(centerY + Math.sin(angle) * radius),
        isCenter: false,
      };
    });

    const relevantEdges = GRAPH_EDGES.filter(
      (e) => connectedNodeIds.has(e.from) && connectedNodeIds.has(e.to)
    );

    return { nodes: positionedNodes, edges: relevantEdges };
  }, [selectedNode, directOutgoingEdges, directIncomingEdges]);

  // Cypher query representation
  const activeCypher = useMemo(() => {
    if (!selectedNode) return "";
    return `// FalkorDB Cypher Engine Query
MATCH (n:${selectedNode.label} {id: '${selectedNode.id}'})
OPTIONAL MATCH (n)-[r:USES_ORACLE|DEPENDS_ON|GOVERNED_BY|DEPLOYED_ON]->(dep)
RETURN n.display_name AS Source, type(r) AS Relationship, dep.display_name AS Target;`;
  }, [selectedNode]);

  const stats = useMemo(() => {
    const protocols = GRAPH_NODES.filter((n) => n.label === "Protocol").length;
    const oracles = GRAPH_NODES.filter((n) => n.label === "Oracle").length;
    const chains = GRAPH_NODES.filter((n) => n.label === "Chain").length;
    const controllers = GRAPH_NODES.filter((n) => n.label === "Controller").length;
    const assets = GRAPH_NODES.filter((n) => n.label === "Stablecoin").length;
    return { protocols, oracles, chains, controllers, assets, totalNodes: GRAPH_NODES.length, totalEdges: GRAPH_EDGES.length };
  }, []);

  return (
    <div className="space-y-6">
      {/* Top Banner: FalkorDB Engine Status */}
      <div className="bg-[#ffffff] border border-[#d8d4d4] rounded-[4px] p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="flex h-3 w-3 relative">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
            <span className="relative inline-flex rounded-full h-3 w-3 bg-emerald-500"></span>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <span className="font-mono text-[12px] font-bold text-[#181011]">
                FalkorDB v2.8 (GraphBLAS Engine)
              </span>
              <span className="text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200 px-1.5 py-0.5 rounded font-mono">
                LIVE: :6379
              </span>
            </div>
            <div className="text-[11px] font-mono text-[#666666]">
              Graphs: <span className="font-semibold text-[#181011]">defi_risk</span> (104 nodes, 164 edges) · <span className="font-semibold text-[#181011]">mem_demo_trader</span> (5 nodes, 9 edges) · <span className="font-semibold text-[#181011]">defi_evidence</span> (3 nodes)
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {CYPHER_PRESETS.map((preset, idx) => (
            <button
              key={idx}
              onClick={() => setSelectedNodeId(preset.nodeId)}
              className="text-[11px] font-mono px-2.5 py-1 rounded border border-[#d8d4d4] bg-[#f3f1ed] hover:bg-[#ffffff] text-[#181011] transition-colors"
            >
              {preset.title}
            </button>
          ))}
        </div>
      </div>

      {/* Main Grid: Visual Graph Canvas (Left 8 Cols) and Cypher / Inspector (Right 4 Cols) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Interactive Topology Canvas */}
        <div className="lg:col-span-8 bg-[#ffffff] border border-[#d8d4d4] rounded-[4px] p-4 space-y-4 shadow-xs">
          {/* Canvas Controls Header */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#d8d4d4] pb-3">
            <div className="flex items-center gap-2">
              <span className="font-mono text-[12px] font-bold uppercase tracking-wider text-[#181011]">
                Graph Topology &amp; 1-Hop Neighborhood
              </span>
              <span className="text-[10px] font-mono bg-[#f3f1ed] text-[#666666] px-2 py-0.5 rounded border border-[#d8d4d4]">
                {focalGraph.nodes.length} visible entities · {focalGraph.edges.length} active edges
              </span>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={() => setZoomLevel((z) => Math.max(0.7, z - 0.15))}
                className="w-7 h-7 flex items-center justify-center font-mono text-xs border border-[#d8d4d4] rounded bg-[#ffffff] hover:bg-[#f3f1ed]"
                title="Zoom Out"
              >
                -
              </button>
              <span className="font-mono text-[11px] text-[#666666] w-12 text-center">
                {Math.round(zoomLevel * 100)}%
              </span>
              <button
                onClick={() => setZoomLevel((z) => Math.min(1.5, z + 0.15))}
                className="w-7 h-7 flex items-center justify-center font-mono text-xs border border-[#d8d4d4] rounded bg-[#ffffff] hover:bg-[#f3f1ed]"
                title="Zoom In"
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

          {/* SVG Interactive Canvas */}
          <div className="relative border border-[#d8d4d4] rounded bg-[#faf9f8] overflow-hidden select-none h-[480px]">
            <svg
              className="w-full h-full"
              viewBox="0 0 720 480"
              style={{
                transform: `scale(${zoomLevel})`,
                transformOrigin: "center center",
                transition: "transform 0.2s ease-out",
              }}
            >
              <defs>
                <marker
                  id="arrow-default"
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
                  id="arrow-active"
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
              {focalGraph.edges.map((edge) => {
                const source = focalGraph.nodes.find((n) => n.id === edge.from);
                const target = focalGraph.nodes.find((n) => n.id === edge.to);
                if (!source || !target) return null;

                const isConnectedToSelected =
                  edge.from === selectedNode?.id || edge.to === selectedNode?.id;

                const midX = (source.x + target.x) / 2;
                const midY = (source.y + target.y) / 2;

                return (
                  <g key={edge.id} className="cursor-pointer">
                    <line
                      x1={source.x}
                      y1={source.y}
                      x2={target.x}
                      y2={target.y}
                      stroke={isConnectedToSelected ? "#181011" : "#cccccc"}
                      strokeWidth={isConnectedToSelected ? 2 : 1}
                      strokeDasharray={edge.type === "GOVERNED_BY" ? "4,4" : undefined}
                      markerEnd={isConnectedToSelected ? "url(#arrow-active)" : "url(#arrow-default)"}
                    />
                    {isConnectedToSelected && (
                      <text
                        x={midX}
                        y={midY - 4}
                        textAnchor="middle"
                        className="text-[9px] font-mono fill-[#666666] bg-white font-bold"
                      >
                        {edge.type}
                      </text>
                    )}
                  </g>
                );
              })}

              {/* Node Circles */}
              {focalGraph.nodes.map((node) => {
                const isSelected = node.id === selectedNode?.id;
                const isHovered = node.id === hoveredNodeId;
                const colors = ENTITY_COLORS[node.label] || ENTITY_COLORS.Default;
                const radius = isSelected ? 28 : node.isCenter ? 26 : 20;

                return (
                  <g
                    key={node.id}
                    transform={`translate(${node.x}, ${node.y})`}
                    className="cursor-pointer"
                    onClick={() => setSelectedNodeId(node.id)}
                    onMouseEnter={() => setHoveredNodeId(node.id)}
                    onMouseLeave={() => setHoveredNodeId(null)}
                  >
                    {/* Glow ring for selected node */}
                    {isSelected && (
                      <circle
                        r={radius + 6}
                        fill="none"
                        stroke="#181011"
                        strokeWidth="2"
                        strokeDasharray="3,3"
                        className="animate-spin"
                        style={{ transformOrigin: "0 0" }}
                      />
                    )}

                    {/* Node base circle */}
                    <circle
                      r={radius}
                      fill={colors.bg}
                      stroke={isSelected ? "#181011" : colors.border}
                      strokeWidth={isSelected ? 2.5 : 1.5}
                    />

                    {/* Node Dot / Indicator */}
                    <circle cx="0" cy={-radius + 7} r="3" fill={colors.dot} />

                    {/* Node Label Text */}
                    <text
                      textAnchor="middle"
                      y={4}
                      className="text-[10px] font-mono font-bold fill-[#181011] pointer-events-none"
                    >
                      {node.name.length > 10 ? node.name.slice(0, 9) + "…" : node.name}
                    </text>

                    {/* Entity Type Label */}
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

            {/* Entity Type Legend */}
            <div className="absolute bottom-3 left-3 bg-[#ffffff]/90 backdrop-blur-xs border border-[#d8d4d4] rounded p-2 flex flex-wrap items-center gap-2 text-[10px] font-mono">
              <span className="text-[#888888] uppercase">Legend:</span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-blue-500"></span> Protocol
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-amber-500"></span> Oracle
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-purple-500"></span> Controller
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-emerald-500"></span> Chain
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-teal-500"></span> Stablecoin
              </span>
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-red-500"></span> Incident
              </span>
            </div>
          </div>

          {/* Quick Entity Selector & Search Bar */}
          <div className="space-y-2 pt-2">
            <div className="flex flex-col sm:flex-row items-center justify-between gap-2">
              <div className="relative w-full sm:w-64">
                <input
                  type="text"
                  placeholder="Search 108 nodes in FalkorDB..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full text-[12px] font-mono px-3 py-1.5 border border-[#d8d4d4] rounded bg-[#ffffff] focus:outline-none focus:border-[#181011]"
                />
              </div>

              {/* Filter Pills */}
              <div className="flex flex-wrap items-center gap-1 overflow-x-auto w-full sm:w-auto">
                {["All", "Protocol", "Oracle", "Controller", "Chain", "Stablecoin"].map((type) => (
                  <button
                    key={type}
                    onClick={() => setFilterType(type)}
                    className={`px-2 py-1 text-[11px] font-mono rounded transition-colors ${
                      filterType === type
                        ? "bg-[#181011] text-[#ffffff]"
                        : "bg-[#f3f1ed] text-[#666666] border border-[#d8d4d4] hover:bg-[#ffffff]"
                    }`}
                  >
                    {type}
                  </button>
                ))}
              </div>
            </div>

            {/* Quick Node List Chips */}
            <div className="flex flex-wrap gap-1.5 max-h-24 overflow-y-auto p-1 bg-[#faf9f8] border border-[#d8d4d4] rounded">
              {filteredNodes.slice(0, 30).map((n) => (
                <button
                  key={n.id}
                  onClick={() => setSelectedNodeId(n.id)}
                  className={`px-2 py-0.5 text-[11px] font-mono rounded border transition-colors ${
                    selectedNode?.id === n.id
                      ? "bg-[#181011] text-[#ffffff] border-[#181011]"
                      : "bg-[#ffffff] text-[#181011] border-[#d8d4d4] hover:border-[#888888]"
                  }`}
                >
                  {n.name}
                </button>
              ))}
              {filteredNodes.length > 30 && (
                <span className="text-[10px] font-mono text-[#888888] self-center pl-1">
                  +{filteredNodes.length - 30} more
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Node Details & Live FalkorDB Cypher Console */}
        <div className="lg:col-span-4 space-y-4">
          {/* Node Inspector Card */}
          <div className="bg-[#ffffff] border border-[#d8d4d4] rounded-[4px] p-5 space-y-4 shadow-xs">
            <div className="flex items-center justify-between border-b border-[#d8d4d4] pb-3">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-wider px-1.5 py-0.5 rounded bg-[#f3f1ed] text-[#181011] border border-[#d8d4d4]">
                  {selectedNode?.label}
                </span>
                <h3 className="text-[18px] font-bold text-[#181011] mt-1.5">
                  {selectedNode?.name}
                </h3>
              </div>

              {/* Action Buttons */}
              <div className="flex flex-col gap-1.5">
                {selectedNode?.label === "Protocol" && (
                  <button
                    onClick={() => onAuditProtocol(selectedNode.id)}
                    className="px-3 py-1 bg-[#181011] text-[#ffffff] text-[11px] font-mono rounded hover:bg-[#302023] transition-colors"
                  >
                    Audit Protocol ➔
                  </button>
                )}
                <button
                  onClick={() => onSimulateShock(selectedNode.id)}
                  className="px-3 py-1 bg-[#ffffff] border border-[#d8d4d4] text-[#181011] text-[11px] font-mono rounded hover:bg-[#f3f1ed] transition-colors"
                >
                  Shock Node ⚡
                </button>
              </div>
            </div>

            {/* Properties Grid */}
            <div className="grid grid-cols-2 gap-2 text-[11px] font-mono bg-[#faf9f8] p-3 rounded border border-[#e5e5e5]">
              <div>
                <span className="text-[#888888] block text-[10px]">ENTITY ID</span>
                <span className="text-[#181011] font-semibold truncate block" title={selectedNode?.id}>
                  {selectedNode?.id}
                </span>
              </div>
              <div>
                <span className="text-[#888888] block text-[10px]">CATEGORY</span>
                <span className="text-[#181011] font-semibold">
                  {selectedNode?.category || selectedNode?.kind || "Infrastructure"}
                </span>
              </div>
              {selectedNode?.tvl_usd !== undefined && (
                <div>
                  <span className="text-[#888888] block text-[10px]">VERIFIED TVL</span>
                  <span className="text-[#181011] font-semibold">
                    ${(selectedNode.tvl_usd / 1e9).toFixed(2)}B
                  </span>
                </div>
              )}
              {selectedNode?.audits !== undefined && (
                <div>
                  <span className="text-[#888888] block text-[10px]">SECURITY AUDITS</span>
                  <span className="text-[#181011] font-semibold">
                    {selectedNode.audits ?? "None"} Verified
                  </span>
                </div>
              )}
              {selectedNode?.controllerType && (
                <div className="col-span-2">
                  <span className="text-[#888888] block text-[10px]">GOVERNANCE CONTROLLER</span>
                  <span className="text-[#181011] font-semibold">
                    {selectedNode.controllerType.toUpperCase()} ({selectedNode.threshold} signers, {selectedNode.timelockHours}h delay)
                  </span>
                </div>
              )}
              {selectedNode?.sourceUrl && (
                <div className="col-span-2 truncate">
                  <span className="text-[#888888] block text-[10px]">SOURCE OF PROVENANCE</span>
                  <a
                    href={selectedNode.sourceUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="text-blue-600 underline font-mono text-[10px] hover:text-blue-800"
                  >
                    {selectedNode.sourceUrl}
                  </a>
                </div>
              )}
            </div>

            {/* Verified Direct Dependencies */}
            <div className="space-y-2">
              <div className="flex items-center justify-between text-[10px] font-mono uppercase tracking-wider text-[#888888]">
                <span>Outgoing Dependencies ({directOutgoingEdges.length})</span>
                <span className="text-emerald-600 font-bold">VERIFIED EDGES</span>
              </div>
              {directOutgoingEdges.length === 0 ? (
                <div className="text-[11px] font-mono text-[#888888] italic p-2 bg-[#faf9f8] rounded">
                  No outgoing dependencies recorded in FalkorDB.
                </div>
              ) : (
                <div className="space-y-1.5 max-h-36 overflow-y-auto">
                  {directOutgoingEdges.map((e) => {
                    const target = GRAPH_NODES.find((n) => n.id === e.to);
                    return (
                      <div
                        key={e.id}
                        onClick={() => setSelectedNodeId(e.to)}
                        className="p-2 border border-[#d8d4d4] rounded bg-[#ffffff] hover:bg-[#faf9f8] cursor-pointer flex items-center justify-between text-[11px] font-mono"
                      >
                        <span className="font-semibold text-[#181011] truncate">{target?.name || e.to}</span>
                        <span className="text-[9px] bg-[#f3f1ed] text-[#181011] px-1.5 py-0.5 rounded border border-[#d8d4d4]">
                          {e.type}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Dependent Protocols (Incoming) */}
            {directIncomingEdges.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-[#d8d4d4]">
                <div className="text-[10px] font-mono uppercase tracking-wider text-[#888888]">
                  Incoming Dependents ({directIncomingEdges.length})
                </div>
                <div className="space-y-1.5 max-h-28 overflow-y-auto">
                  {directIncomingEdges.map((e) => {
                    const src = GRAPH_NODES.find((n) => n.id === e.from);
                    return (
                      <div
                        key={e.id}
                        onClick={() => setSelectedNodeId(e.from)}
                        className="p-1.5 border border-[#e5e5e5] rounded bg-[#faf9f8] hover:bg-[#ffffff] cursor-pointer flex items-center justify-between text-[10px] font-mono"
                      >
                        <span className="text-[#181011] truncate">{src?.name || e.from}</span>
                        <span className="text-[#888888]">{e.type}</span>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
          </div>

          {/* Live FalkorDB Cypher Query Terminal */}
          <div className="bg-[#181011] text-[#f3f1ed] border border-[#302023] rounded-[4px] p-4 space-y-2 font-mono">
            <div className="flex items-center justify-between border-b border-[#302023] pb-2 text-[10px] text-[#aaaaaa]">
              <div className="flex items-center gap-1.5">
                <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
                <span>FALKORDB CYPHER TERMINAL</span>
              </div>
              <span>PORT 6379</span>
            </div>

            <pre className="text-[11px] text-emerald-400 overflow-x-auto p-2 bg-[#0c0808] rounded border border-[#302023] leading-relaxed">
              {activeCypher}
            </pre>

            <div className="flex items-center justify-between text-[10px] text-[#888888] pt-1">
              <span>GraphBLAS Traversal: &lt;1.2ms</span>
              <span>Deterministic Memory Gate</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
