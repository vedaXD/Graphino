import React, { useState } from "react";
import { simulateShock, computeSystemicImportance } from "@/lib/engine/contagion";
import { PortfolioPosition } from "@/lib/types";

interface ContagionEngineViewProps {
  positions: PortfolioPosition[];
  onAuditProtocol: (protocolId: string) => void;
}

export const ContagionEngineView: React.FC<ContagionEngineViewProps> = ({
  positions,
  onAuditProtocol,
}) => {
  const [targetNodeId, setTargetNodeId] = useState<string>("chainlink-price-feeds");
  const [severity, setSeverity] = useState<number>(0.8);

  const simulation = simulateShock(targetNodeId, severity, 3, positions);
  const systemicLeaderboard = computeSystemicImportance().slice(0, 5);

  const shockCandidates = [
    { id: "chainlink-price-feeds", name: "Chainlink Decentralized Oracle Feeds" },
    { id: "usdx-algo-stable", name: "USDX Algorithmic Dollar (Depeg)" },
    { id: "eoa-admin-deployer", name: "Apex Master Deployer EOA (Key Backdoor)" },
    { id: "usdc", name: "USD Coin (USDC Reserve Depeg)" },
    { id: "lido-accounting-oracle", name: "Lido Consensus Accounting Oracle" },
  ];

  return (
    <section id="contagion" className="space-y-6 pt-10 border-t border-[#d8d4d4] scroll-mt-20">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 border-b border-[#d8d4d4] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="tracked-badge text-[10px]">CONTAGION ENGINE</span>
            <span className="text-[#aaaaaa] text-xs font-mono">BACKWARD BFS</span>
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
              Failure Origin Node
            </label>
            <select
              value={targetNodeId}
              onChange={(e) => setTargetNodeId(e.target.value)}
              className="w-full bg-[#f3f1ed] border border-[#d8d4d4] rounded-[4px] px-3 py-2 text-[14px] text-[#181011] focus:outline-none focus:border-[#181011]"
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
          </div>
          <div className="p-4 bg-[#f3f1ed] rounded-[4px] border border-[#d8d4d4]">
            <div className="text-[10px] font-mono uppercase tracking-[0.10em] text-[#aaaaaa]">
              Portfolio Capital at Risk
            </div>
            <div className="text-[26px] font-mono text-[#181011] mt-0.5">
              ${simulation.total_portfolio_loss_usd.toLocaleString()} USD
            </div>
          </div>
          <div className="p-4 bg-[#f3f1ed] rounded-[4px] border border-[#d8d4d4]">
            <div className="text-[10px] font-mono uppercase tracking-[0.10em] text-[#aaaaaa]">
              Loss Exposure
            </div>
            <div className="text-[26px] font-mono text-[#181011] mt-0.5">
              {simulation.portfolio_at_risk_pct}%
            </div>
          </div>
        </div>
      </div>

      {/* Contagion Blast Radius Compact Table */}
      <div className="surface-white overflow-hidden">
        <div className="p-4 bg-[#f3f1ed] border-b border-[#d8d4d4] flex items-center justify-between">
          <span className="tracked-badge text-[9px]">CONTAGION CASCADE PATHS</span>
          <span className="text-[11px] font-mono text-[#666666]">MAX DEPTH: 3 HOPS</span>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[13px] divide-y divide-[#d8d4d4]">
            <tbody className="divide-y divide-[#d8d4d4] bg-[#ffffff]">
              {simulation.impacted_protocols.map((item) => (
                <tr key={item.protocol_id} className="hover:bg-[#f3f1ed]/40 transition-colors">
                  <td className="py-3 px-4">
                    <span className="font-bold text-[#181011]">{item.name}</span>
                    <span className="block text-[11px] font-mono text-[#aaaaaa]">{item.protocol_id}</span>
                  </td>
                  <td className="py-3 px-4 font-mono">
                    <span className="tracked-badge text-[9px]">{item.hops} HOP{item.hops > 1 ? "S" : ""}</span>
                  </td>
                  <td className="py-3 px-4 font-mono text-[11px] text-[#666666] truncate max-w-xs">
                    {item.path.join(" ➔ ")}
                  </td>
                  <td className="py-3 px-4 font-mono">
                    <span className="text-[#181011] font-bold">
                      {(item.contagion_fraction * 100).toFixed(0)}% impact
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <button
                      onClick={() => onAuditProtocol(item.protocol_id)}
                      className="square-btn text-[11px] py-1 px-2.5"
                    >
                      Audit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Systemic PageRank Leaderboard */}
      <div className="surface-white p-5 space-y-3">
        <div className="flex items-center justify-between border-b border-[#d8d4d4] pb-2">
          <div className="flex items-center gap-2">
            <span className="tracked-badge text-[9px]">SYSTEMIC PAGERANK</span>
            <span className="text-[12px] font-mono text-[#181011]">Top Critical Nodes</span>
          </div>
          <span className="text-[11px] font-mono text-[#aaaaaa]">OVER ELIGIBLE EDGES</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-5 gap-3 font-mono text-[12px]">
          {systemicLeaderboard.map((item) => (
            <div key={item.id} className="p-3 bg-[#f3f1ed] rounded-[4px] border border-[#d8d4d4] space-y-1">
              <div className="text-[10px] text-[#aaaaaa] uppercase">{item.label}</div>
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
