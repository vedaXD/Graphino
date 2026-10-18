import React, { useState } from "react";
import { simulateShock, computeSystemicImportance } from "@/lib/engine/contagion";
import { PortfolioPosition } from "@/lib/types";

interface ContagionEngineViewProps {
  positions: PortfolioPosition[];
  initialTargetNodeId?: string;
  onAuditProtocol: (protocolId: string) => void;
}

export const ContagionEngineView: React.FC<ContagionEngineViewProps> = ({
  positions,
  initialTargetNodeId = "chainlink-price-feeds",
  onAuditProtocol,
}) => {
  const [targetNodeId, setTargetNodeId] = useState<string>(initialTargetNodeId);
  const [severity, setSeverity] = useState<number>(0.8);

  const simulation = simulateShock(targetNodeId, severity, 3, positions);
  const systemicLeaderboard = computeSystemicImportance().slice(0, 5);

  const shockCandidates = [
    { id: "chainlink-price-feeds", name: "Chainlink Price Feeds (Oracle)" },
    { id: "chainlink-node-operators", name: "Chainlink Node Operator Network (Multi-Hop Cascade)" },
    { id: "lido-accounting-oracle", name: "Lido AccountingOracle (Oracle)" },
    { id: "aave-governance", name: "Aave Governance (Controller)" },
    { id: "1", name: "Ethereum L1 Mainnet (Chain Outage)" },
    { id: "42161", name: "Arbitrum One (L2 Rollup Outage)" },
    { id: "8453", name: "Base (L2 Rollup Outage)" },
    { id: "solana", name: "Solana Network (Chain Outage)" },
    { id: "stablecoin:1", name: "Tether USD₮ (Stablecoin Reserve Shock)" },
    { id: "stablecoin:2", name: "USD Coin USDC (Stablecoin Reserve Shock)" },
    { id: "stablecoin:14", name: "USDD TRON Reserve (Stablecoin Shock)" },
  ];

  return (
    <section id="contagion" className="space-y-6 pt-4 scroll-mt-20">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 border-b border-[#d8d4d4] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="tracked-badge text-[10px]">CONTAGION ENGINE</span>
            <span className="text-[#aaaaaa] text-xs font-mono">MULTI-HOP BACKWARD BFS</span>
          </div>
          <h2 className="text-[26px] sm:text-[30px] font-normal text-[#181011] tracking-[-0.02em]">
            Multi-Hop Failure Contagion &amp; Systemic PageRank
          </h2>
        </div>
      </div>

      {/* Control Box: 1 Origin Select + 1 Severity Slider */}
      <div className="surface-white p-6 space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-end">
          <div className="md:col-span-6 space-y-1.5">
            <label className="text-[11px] font-mono uppercase tracking-[0.10em] text-[#666666]">
              Failure Origin Component (Shock Source)
            </label>
            <select
              value={targetNodeId}
              onChange={(e) => setTargetNodeId(e.target.value)}
              className="w-full bg-[#f3f1ed] border border-[#d8d4d4] rounded-[4px] px-3 py-2 text-[14px] text-[#181011] focus:outline-none focus:border-[#181011] font-mono cursor-pointer"
            >
              {shockCandidates.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </div>

          <div className="md:col-span-6 space-y-1.5">
            <div className="flex justify-between items-center text-[11px] font-mono uppercase tracking-[0.10em] text-[#666666]">
              <span>Shock Magnitude</span>
              <span className="text-[#181011] font-bold">{(severity * 100).toFixed(0)}% Outage</span>
            </div>
            <input
              type="range"
              min="0.1"
              max="1.0"
              step="0.05"
              value={severity}
              onChange={(e) => setSeverity(parseFloat(e.target.value))}
              className="w-full accent-[#181011] cursor-pointer"
            />
          </div>
        </div>

        {/* 3 Prominent Metric Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 border-t border-[#d8d4d4]">
          <div className="p-4 bg-[#f3f1ed] rounded-[4px] border border-[#d8d4d4]">
            <div className="text-[10px] font-mono uppercase tracking-[0.10em] text-[#aaaaaa]">
              Impacted Protocols
            </div>
            <div className="text-[26px] font-mono text-[#181011] mt-0.5">
              {simulation.impacted_protocols.length}
            </div>
            <div className="text-[10px] font-mono text-[#666666] mt-1">
              {simulation.impacted_protocols.length > 0
                ? "Blast radius across 1-3 hops"
                : "No dependents found"}
            </div>
          </div>

          <div className="p-4 bg-[#f3f1ed] rounded-[4px] border border-[#d8d4d4]">
            <div className="text-[10px] font-mono uppercase tracking-[0.10em] text-[#aaaaaa]">
              Portfolio Capital at Risk
            </div>
            <div className="text-[26px] font-mono text-[#181011] mt-0.5">
              ${simulation.total_portfolio_loss_usd.toLocaleString()} USD
            </div>
            <div className="text-[10px] font-mono text-[#666666] mt-1">
              {simulation.total_portfolio_loss_usd > 0
                ? `${simulation.portfolio_at_risk_pct}% of tenant capital exposed`
                : "No active holdings in blast radius"}
            </div>
          </div>

          <div className="p-4 bg-[#f3f1ed] rounded-[4px] border border-[#d8d4d4]">
            <div className="text-[10px] font-mono uppercase tracking-[0.10em] text-[#aaaaaa]">
              Systemic TVL Exposed
            </div>
            <div className="text-[26px] font-mono text-[#181011] mt-0.5">
              ${((simulation.total_systemic_tvl_at_risk_usd || 0) / 1e9).toFixed(2)}B USD
            </div>
            <div className="text-[10px] font-mono text-[#666666] mt-1">
              Total protocol TVL in cascade path
            </div>
          </div>
        </div>
      </div>

      {/* Contagion Blast Radius Table */}
      <div className="surface-white overflow-hidden">
        <div className="p-4 bg-[#f3f1ed] border-b border-[#d8d4d4] flex items-center justify-between">
          <span className="tracked-badge text-[9px]">CONTAGION CASCADE PATHS</span>
          <span className="text-[11px] font-mono text-[#666666]">
            {simulation.impacted_protocols.length} PROTOCOLS IMPACTED (MAX 3 HOPS)
          </span>
        </div>
        <div className="overflow-x-auto">
          {simulation.impacted_protocols.length === 0 ? (
            <div className="p-8 text-center text-[13px] font-mono text-[#888888]">
              No protocol dependency paths discovered for this node.
            </div>
          ) : (
            <table className="w-full text-left text-[13px] divide-y divide-[#d8d4d4]">
              <thead className="bg-[#f9f8f6] text-[10px] font-mono uppercase tracking-wider text-[#666666]">
                <tr>
                  <th className="py-2.5 px-4">Protocol</th>
                  <th className="py-2.5 px-4">Hops</th>
                  <th className="py-2.5 px-4">Cascade Path</th>
                  <th className="py-2.5 px-4">Contagion Impact</th>
                  <th className="py-2.5 px-4">Protocol TVL</th>
                  <th className="py-2.5 px-4">Portfolio Loss</th>
                  <th className="py-2.5 px-4 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#d8d4d4] bg-[#ffffff]">
                {simulation.impacted_protocols.map((item) => (
                  <tr key={item.protocol_id} className="hover:bg-[#f3f1ed]/40 transition-colors">
                    <td className="py-3 px-4">
                      <span className="font-bold text-[#181011]">{item.name}</span>
                      <span className="block text-[11px] font-mono text-[#aaaaaa]">{item.protocol_id}</span>
                    </td>
                    <td className="py-3 px-4 font-mono">
                      <span className="tracked-badge text-[9px]">
                        {item.hops} HOP{item.hops > 1 ? "S" : ""}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-[11px] text-[#666666] truncate max-w-xs">
                      {item.path.join(" ➔ ")}
                    </td>
                    <td className="py-3 px-4 font-mono">
                      <span className="text-[#181011] font-bold">
                        {(item.contagion_fraction * 100).toFixed(0)}% impact
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-[11px] text-[#444444]">
                      {item.tvl_usd ? `$${(item.tvl_usd / 1e9).toFixed(2)}B` : "-"}
                    </td>
                    <td className="py-3 px-4 font-mono text-[12px]">
                      {item.estimated_position_loss_usd > 0 ? (
                        <span className="text-red-700 font-bold">
                          ${item.estimated_position_loss_usd.toLocaleString()} USD
                        </span>
                      ) : (
                        <span className="text-[#aaaaaa]">$0.00</span>
                      )}
                    </td>
                    <td className="py-3 px-4 text-right">
                      <button
                        onClick={() => onAuditProtocol(item.protocol_id)}
                        className="square-btn text-[11px] py-1 px-2.5 cursor-pointer"
                      >
                        Audit
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>

      {/* Systemic PageRank Leaderboard */}
      <div className="surface-white p-5 space-y-3">
        <div className="flex items-center justify-between border-b border-[#d8d4d4] pb-2">
          <div className="flex items-center gap-2">
            <span className="tracked-badge text-[9px]">SYSTEMIC PAGERANK</span>
            <span className="text-[12px] font-mono text-[#181011]">Top Critical Infrastructure Nodes</span>
          </div>
          <span className="text-[11px] font-mono text-[#aaaaaa]">FALKORDB GRAPHBLAS TOPOLOGY</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 font-mono text-[12px]">
          {systemicLeaderboard.map((item) => (
            <div key={item.id} className="p-3 bg-[#f3f1ed] rounded-[4px] border border-[#d8d4d4] space-y-1">
              <div className="flex items-center justify-between text-[10px]">
                <span className="text-[#aaaaaa] uppercase">{item.label}</span>
                <span
                  className={`text-[8px] px-1 py-0.2 rounded font-bold ${
                    item.systemic_tier === "CRITICAL"
                      ? "bg-red-100 text-red-700"
                      : item.systemic_tier === "HIGH"
                      ? "bg-amber-100 text-amber-700"
                      : "bg-emerald-100 text-emerald-700"
                  }`}
                >
                  {item.systemic_tier}
                </span>
              </div>
              <div className="font-bold text-[#181011] truncate">{item.name}</div>
              <div className="text-[11px] text-[#666666] flex justify-between pt-1 border-t border-[#d8d4d4]">
                <span>PageRank</span>
                <span className="text-[#181011] font-bold">{item.pagerank_score.toFixed(3)}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
