import React, { useState } from "react";
import { GRAPH_NODES } from "@/lib/data/graphData";
import { assessProposal, issueGateToken } from "@/lib/engine/riskEngine";
import { Proposal, Verdict, GateToken, UserProfile } from "@/lib/types";

interface ProposalGateViewProps {
  userProfile: UserProfile;
  initialProtocolId?: string;
  onTradeExecuted: (protocolId: string, amountUsd: number, token: string) => void;
}

export const ProposalGateView: React.FC<ProposalGateViewProps> = ({
  userProfile,
  initialProtocolId = "young-fork-protocol",
  onTradeExecuted,
}) => {
  const [protocolId, setProtocolId] = useState<string>(initialProtocolId);
  const [amountUsd, setAmountUsd] = useState<number>(100000);
  const [verdict, setVerdict] = useState<Verdict | null>(() =>
    assessProposal({ protocol_id: initialProtocolId, amount_usd: 100000 }, userProfile)
  );
  const [gateToken, setGateToken] = useState<GateToken | null>(() => {
    const v = assessProposal({ protocol_id: initialProtocolId, amount_usd: 100000 }, userProfile);
    return issueGateToken(v);
  });
  const [executionMessage, setExecutionMessage] = useState<string | null>(null);

  const availableProtocols = GRAPH_NODES.filter((n) => n.label === "Protocol");

  const handleRunAssessment = () => {
    const proposal: Proposal = {
      protocol_id: protocolId,
      amount_usd: amountUsd,
    };
    const evaluated = assessProposal(proposal, userProfile);
    setVerdict(evaluated);
    setGateToken(issueGateToken(evaluated));
    setExecutionMessage(null);
  };

  const handleExecutePaperTrade = () => {
    if (!verdict || !gateToken) return;
    onTradeExecuted(verdict.proposal.protocol_id, verdict.allowed_amount_usd, gateToken.token);
    setExecutionMessage(
      `✓ Executed paper position of $${verdict.allowed_amount_usd.toLocaleString()} on ${verdict.proposal.protocol_id}.`
    );
  };

  return (
    <section id="assessment" className="space-y-6 pt-10 border-t border-[#d8d4d4] scroll-mt-20">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 border-b border-[#d8d4d4] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="tracked-badge text-[10px]">DETERMINISTIC ACTION GATE</span>
            <span className="text-[#aaaaaa] text-xs font-mono">RULES R1-R9 · S1</span>
          </div>
          <h2 className="text-[26px] sm:text-[30px] font-normal text-[#181011] tracking-[-0.02em]">
            Proposal Risk Assessment &amp; Gate Execution
          </h2>
        </div>
      </div>

      {/* Clean Interactive Proposal Bar */}
      <div className="surface-white p-6 space-y-5">
        <div className="grid grid-cols-1 sm:grid-cols-12 gap-4 items-end">
          <div className="sm:col-span-5 space-y-1.5">
            <label className="text-[11px] font-mono uppercase tracking-[0.10em] text-[#666666]">
              Target Protocol
            </label>
            <select
              value={protocolId}
              onChange={(e) => setProtocolId(e.target.value)}
              className="w-full bg-[#f3f1ed] border border-[#d8d4d4] rounded-[4px] px-3 py-2 text-[14px] text-[#181011] focus:outline-none focus:border-[#181011] font-mono cursor-pointer"
            >
              {availableProtocols.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.id})
                </option>
              ))}
            </select>
          </div>

          <div className="sm:col-span-4 space-y-1.5">
            <label className="text-[11px] font-mono uppercase tracking-[0.10em] text-[#666666]">
              Proposed Allocation (USD)
            </label>
            <input
              type="number"
              step="10000"
              value={amountUsd}
              onChange={(e) => setAmountUsd(Math.max(1000, Number(e.target.value)))}
              className="w-full bg-[#f3f1ed] border border-[#d8d4d4] rounded-[4px] px-3 py-2 text-[14px] text-[#181011] focus:outline-none focus:border-[#181011] font-mono"
            />
          </div>

          <div className="sm:col-span-3">
            <button
              onClick={handleRunAssessment}
              className="w-full pill-cta py-2 text-[14px]"
            >
              Run Assessment
            </button>
          </div>
        </div>
      </div>

      {/* Verdict Output Banner & Findings */}
      {verdict && (
        <div className="space-y-4">
          <div className="surface-white p-5 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#d8d4d4] pb-4">
              <div>
                <span className="text-[10px] font-mono uppercase tracking-[0.10em] text-[#aaaaaa]">
                  DETERMINISTIC VERDICT
                </span>
                <div className="flex items-center gap-3 mt-1">
                  <span
                    className={`px-3 py-1 rounded-[4px] text-[15px] font-mono font-bold tracking-[0.05em] uppercase border ${
                      verdict.outcome === "BLOCK"
                        ? "bg-[#302023] text-[#ffffff] border-[#181011]"
                        : verdict.outcome === "ALLOW_WITH_CAP"
                        ? "bg-[#181011] text-[#ffffff] border-[#181011]"
                        : "bg-[#ffffff] text-[#181011] border-[#181011]"
                    }`}
                  >
                    {verdict.outcome}
                  </span>
                  <span className="text-[14px] text-[#666666]">
                    for proposed ${verdict.proposal.amount_usd.toLocaleString()}
                  </span>
                </div>
              </div>

              <div className="sm:text-right">
                <span className="text-[10px] font-mono uppercase tracking-[0.10em] text-[#aaaaaa]">
                  Permitted Limit
                </span>
                <div className="text-[24px] font-mono font-bold text-[#181011]">
                  ${verdict.allowed_amount_usd.toLocaleString()} USD
                </div>
              </div>
            </div>

            {/* Triggered Rule Findings */}
            <div className="space-y-2.5">
              <div className="text-[10px] font-mono uppercase tracking-[0.10em] text-[#aaaaaa]">
                Triggered Safety Findings ({verdict.findings.length})
              </div>
              {verdict.findings.map((f) => (
                <div
                  key={f.id}
                  className="p-3.5 border border-[#d8d4d4] rounded-[4px] bg-[#f3f1ed]/40 space-y-1.5"
                >
                  <div className="flex items-center justify-between text-[11px] font-mono">
                    <span className="font-bold text-[#181011]">RULE {f.rule} · {f.severity.toUpperCase()}</span>
                    <span className="tracked-badge text-[9px]">{f.action.toUpperCase()}</span>
                  </div>
                  <p className="text-[13px] text-[#222222]">{f.message}</p>
                  {f.path.length > 1 && (
                    <div className="text-[11px] font-mono text-[#666666]">
                      Path: {f.path.join(" ➔ ")}
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Execution Strip */}
            <div className="pt-3 border-t border-[#d8d4d4] flex flex-col sm:flex-row sm:items-center justify-between gap-3">
              <div className="text-[12px] font-mono text-[#181011]">
                {gateToken ? (
                  <span>✓ HMAC Token Sealed: <span className="font-bold">{gateToken.hmac_signature}</span></span>
                ) : (
                  <span className="text-[#302023] font-bold">✕ Action Gate Closed (Block Outcome)</span>
                )}
                {executionMessage && (
                  <span className="block text-[#181011] mt-1">{executionMessage}</span>
                )}
              </div>

              {gateToken && (
                <button
                  onClick={handleExecutePaperTrade}
                  className="pill-cta text-[13px] py-1.5 px-5"
                >
                  Execute Paper Allocation
                </button>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
};
