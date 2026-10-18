import React, { useState } from "react";
import { GRAPH_NODES, GRAPH_EDGES } from "@/lib/data/graphData";
import { EntityType } from "@/lib/types";
import { getEligibleDependencyPaths } from "@/lib/engine/riskEngine";

interface GraphExplorerViewProps {
  onAuditProtocol: (protocolId: string) => void;
  onSimulateShock: (nodeId: string) => void;
}

export const GraphExplorerView: React.FC<GraphExplorerViewProps> = ({
  onAuditProtocol,
  onSimulateShock,
}) => {
  const [selectedFilter, setSelectedFilter] = useState<EntityType | "All">("All");
  const [selectedNodeId, setSelectedNodeId] = useState<string>("aave-v3");

  const filters: (EntityType | "All")[] = [
    "All",
    "Protocol",
    "Oracle",
    "Controller",
    "Stablecoin",
  ];

  const filteredNodes = GRAPH_NODES.filter((node) => {
    return selectedFilter === "All" || node.label === selectedFilter;
  });

  const selectedNode =
    GRAPH_NODES.find((n) => n.id === selectedNodeId) || filteredNodes[0] || GRAPH_NODES[0];

  const outgoingEdges = GRAPH_EDGES.filter((e) => e.from === selectedNode?.id);
  const multiHopPaths =
    selectedNode?.label === "Protocol"
      ? getEligibleDependencyPaths(selectedNode.id, 3)
      : [];

  return (
    <section id="topology" className="space-y-6 pt-10 scroll-mt-20">
      {/* Minimal Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 border-b border-[#d8d4d4] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="tracked-badge text-[10px]">GRAPH TOPOLOGY</span>
            <span className="text-[#aaaaaa] text-xs font-mono">FALKORDB</span>
          </div>
          <h2 className="text-[26px] sm:text-[30px] font-normal text-[#181011] tracking-[-0.02em]">
            Verified Entity Dependencies &amp; Provenance
          </h2>
        </div>

        {/* Minimal Filter Pills */}
        <div className="flex items-center gap-1.5 overflow-x-auto pb-1">
          {filters.map((filter) => {
            const isActive = selectedFilter === filter;
            return (
              <button
                key={filter}
                onClick={() => setSelectedFilter(filter)}
                className={`px-3 py-1 rounded-[4px] text-[12px] font-mono transition-colors ${
                  isActive
                    ? "bg-[#181011] text-[#f3f1ed]"
                    : "bg-[#ffffff] text-[#181011] border border-[#d8d4d4] hover:bg-[#ffffff]/60"
                }`}
              >
                {filter}
              </button>
            );
          })}
        </div>
      </div>

      {/* Main Grid: Left Clean Node Cards / Right Focused Inspector */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left Column: Clean Cards (7 cols) */}
        <div className="lg:col-span-7 grid grid-cols-1 sm:grid-cols-2 gap-3 max-h-[560px] overflow-y-auto pr-1">
          {filteredNodes.map((node) => {
            const isSelected = selectedNode?.id === node.id;
            return (
              <div
                key={node.id}
                onClick={() => setSelectedNodeId(node.id)}
                className={`p-3.5 rounded-[4px] cursor-pointer transition-all border ${
                  isSelected
                    ? "bg-[#ffffff] border-[#181011] ring-1 ring-[#181011]"
                    : "bg-[#ffffff] border-[#d8d4d4] hover:border-[#181011]/60"
                }`}
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="tracked-badge text-[9px]">{node.label}</span>
                  {node.tvl_usd !== undefined && (
                    <span className="text-[12px] font-mono font-bold text-[#181011]">
                      ${(node.tvl_usd / 1000000000).toFixed(1)}B
                    </span>
                  )}
                  {node.price !== undefined && (
                    <span className="text-[12px] font-mono font-bold text-[#181011]">
                      ${node.price.toFixed(3)}
                    </span>
                  )}
                </div>

                <div className="text-[14px] font-bold text-[#181011] truncate">
                  {node.name}
                </div>

                <div className="flex items-center gap-2 mt-2 pt-2 border-t border-[#d8d4d4]/60 text-[11px] font-mono text-[#666666]">
                  <span>{node.category || node.kind || node.controllerType}</span>
                  {node.audits !== undefined && <span>· {node.audits} audits</span>}
                  {node.age_days !== undefined && <span>· {node.age_days}d</span>}
                </div>
              </div>
            );
          })}
        </div>

        {/* Right Column: Clean Inspector (5 cols) */}
        <div className="lg:col-span-5 surface-white p-5 space-y-4">
          <div className="flex items-center justify-between border-b border-[#d8d4d4] pb-3">
            <div>
              <span className="tracked-badge text-[9px]">{selectedNode.label}</span>
              <h3 className="text-[18px] font-bold text-[#181011] mt-1">
                {selectedNode.name}
              </h3>
            </div>
            <div className="flex gap-2">
              {selectedNode.label === "Protocol" && (
                <button
                  onClick={() => onAuditProtocol(selectedNode.id)}
                  className="pill-cta text-[12px] py-1 px-3"
                >
                  Audit
                </button>
              )}
              <button
                onClick={() => onSimulateShock(selectedNode.id)}
                className="square-btn text-[12px] py-1 px-2.5"
              >
                Shock
              </button>
            </div>
          </div>

          {/* Quick Properties */}
          <div className="grid grid-cols-2 gap-2 text-[12px] font-mono bg-[#f3f1ed] p-3 rounded-[4px]">
            <div>
              <span className="text-[#aaaaaa] block text-[10px]">CATEGORY</span>
              <span className="text-[#181011]">{selectedNode.category || "Infrastructure"}</span>
            </div>
            <div>
              <span className="text-[#aaaaaa] block text-[10px]">VERIFIED AUDITS</span>
              <span className="text-[#181011]">{selectedNode.audits ?? "None Listed"}</span>
            </div>
            {selectedNode.controllerType && (
              <div className="col-span-2">
                <span className="text-[#aaaaaa] block text-[10px]">CONTROLLER</span>
                <span className="text-[#181011] uppercase">
                  {selectedNode.controllerType} ({selectedNode.threshold} signers, {selectedNode.timelockHours}h timelock)
                </span>
              </div>
            )}
            {selectedNode.sourceUrl && (
              <div className="col-span-2 truncate">
                <span className="text-[#aaaaaa] block text-[10px]">OFFICIAL DOCS</span>
                <a
                  href={selectedNode.sourceUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="text-[#181011] underline font-mono text-[11px]"
                >
                  {selectedNode.sourceUrl}
                </a>
              </div>
            )}
          </div>

          {/* Outgoing Verified Dependencies */}
          <div className="space-y-2">
            <div className="text-[10px] font-mono uppercase tracking-[0.10em] text-[#aaaaaa]">
              Direct Dependencies ({outgoingEdges.length})
            </div>
            {outgoingEdges.length === 0 ? (
              <p className="text-[12px] text-[#666666] italic">No outgoing dependencies.</p>
            ) : (
              <div className="space-y-1.5 max-h-36 overflow-y-auto font-mono text-[11px]">
                {outgoingEdges.map((e) => {
                  const target = GRAPH_NODES.find((n) => n.id === e.to);
                  return (
                    <div
                      key={e.id}
                      className="p-2 border border-[#d8d4d4] rounded-[4px] flex items-center justify-between bg-[#ffffff]"
                    >
                      <span className="font-bold text-[#181011]">{target?.name || e.to}</span>
                      <span className="tracked-badge text-[9px]">{e.type}</span>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Multi-hop Traversal Tree */}
          {multiHopPaths.length > 0 && (
            <div className="space-y-1.5 pt-2 border-t border-[#d8d4d4]">
              <div className="text-[10px] font-mono uppercase tracking-[0.10em] text-[#aaaaaa]">
                Multi-Hop Traversal ({multiHopPaths.length} paths)
              </div>
              <div className="space-y-1 font-mono text-[11px] max-h-28 overflow-y-auto">
                {multiHopPaths.map((p, i) => (
                  <div key={i} className="p-1.5 bg-[#f3f1ed] rounded-[4px] text-[#181011] truncate">
                    {p.nodes.join(" ➔ ")}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
};
