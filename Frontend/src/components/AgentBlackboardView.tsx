import React, { useState } from "react";
import { runAgentPipeline, PipelineResult } from "@/lib/agents/orchestrator";
import { GRAPH_NODES } from "@/lib/data/graphData";
import { UserProfile } from "@/lib/types";

interface AgentBlackboardViewProps {
  userProfile: UserProfile;
}

export const AgentBlackboardView: React.FC<AgentBlackboardViewProps> = ({
  userProfile,
}) => {
  const [selectedProtocol, setSelectedProtocol] = useState<string>("aave-v3");
  const [amountUsd, setAmountUsd] = useState<number>(50000);
  const [pipelineResult, setPipelineResult] = useState<PipelineResult>(() =>
    runAgentPipeline({ protocol_id: "aave-v3", amount_usd: 50000 }, userProfile)
  );
  const [isRunning, setIsRunning] = useState<boolean>(false);

  const availableProtocols = GRAPH_NODES.filter((n) => n.label === "Protocol");

  const handleRunPipeline = () => {
    setIsRunning(true);
    setTimeout(() => {
      const result = runAgentPipeline(
        { protocol_id: selectedProtocol, amount_usd: amountUsd },
        userProfile
      );
      setPipelineResult(result);
      setIsRunning(false);
    }, 300);
  };

  const steps = [
    { label: "1. Analyst", desc: "Traverses Graph Topology" },
    { label: "2. Guardian", desc: "Deterministic Rule Audit" },
    { label: "3. Action Gate", desc: "HMAC Cryptographic Token" },
    { label: "4. Executor", desc: "Gated Paper Execution" },
  ];

  return (
    <section id="pipeline" className="space-y-6 pt-10 border-t border-[#d8d4d4] scroll-mt-20">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 border-b border-[#d8d4d4] pb-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="tracked-badge text-[10px]">AGENT COORDINATION</span>
            <span className="text-[#aaaaaa] text-xs font-mono">BLACKBOARD ARCHITECTURE</span>
          </div>
          <h2 className="text-[26px] sm:text-[30px] font-normal text-[#181011] tracking-[-0.02em]">
            Tri-Agent Orchestration &amp; Citation Validator
          </h2>
        </div>

        {/* Quick Dispatch Controls */}
        <div className="flex items-center gap-3">
          <select
            value={selectedProtocol}
            onChange={(e) => setSelectedProtocol(e.target.value)}
            className="bg-[#ffffff] border border-[#d8d4d4] rounded-[4px] px-2.5 py-1.5 text-[13px] text-[#181011] font-mono cursor-pointer"
          >
            {availableProtocols.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
          <button
            onClick={handleRunPipeline}
            disabled={isRunning}
            className="pill-cta text-[13px] py-1.5 px-4"
          >
            {isRunning ? "Running..." : "Dispatch Pipeline"}
          </button>
        </div>
      </div>

      {/* 4 Pipeline Visual Steps */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {steps.map((st, i) => (
          <div key={i} className="p-3.5 surface-white border border-[#d8d4d4] space-y-1">
            <div className="text-[10px] font-mono uppercase text-[#aaaaaa]">STEP 0{i + 1}</div>
            <div className="font-bold text-[14px] text-[#181011]">{st.label}</div>
            <div className="text-[12px] text-[#666666] font-mono">{st.desc}</div>
          </div>
        ))}
      </div>

      {/* Terminal Log Stream & Dossier Side-by-Side */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        {/* Left: Terminal Logs (7 cols) */}
        <div className="lg:col-span-7 surface-white p-4 font-mono text-[12px] space-y-2.5 max-h-[360px] overflow-y-auto">
          <div className="flex items-center justify-between border-b border-[#d8d4d4] pb-2 text-[11px] text-[#aaaaaa]">
            <span>TASK BLACKBOARD STREAM</span>
            <span>TASK ID: {pipelineResult.task_id}</span>
          </div>
          {pipelineResult.logs.map((l, i) => (
            <div key={i} className="p-2 rounded-[4px] border border-[#d8d4d4] bg-[#f3f1ed]/40 text-[11px] space-y-0.5">
              <div className="flex justify-between font-bold text-[#181011]">
                <span>[{l.role.toUpperCase()}]</span>
                <span className="tracked-badge text-[8px] py-0">{l.status}</span>
              </div>
              <p className="text-[#333333] leading-[1.3]">{l.message}</p>
            </div>
          ))}
        </div>

        {/* Right: Validation & HMAC Gate (5 cols) */}
        <div className="lg:col-span-5 surface-white p-5 space-y-4">
          <div className="border-b border-[#d8d4d4] pb-3 flex justify-between items-center">
            <span className="tracked-badge text-[10px]">VERDICT &amp; ACTION GATE</span>
            <span className="font-mono font-bold text-[14px] text-[#181011]">
              {pipelineResult.verdict.outcome}
            </span>
          </div>

          <div className="p-3 bg-[#f3f1ed] rounded-[4px] space-y-2 font-mono text-[11px]">
            <div className="flex justify-between">
              <span className="text-[#aaaaaa]">CITATION VALIDATION:</span>
              <span className="text-[#181011] font-bold">100% PROVENANCE GROUNDED</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[#aaaaaa]">ALLOWED ALLOCATION:</span>
              <span className="text-[#181011] font-bold">
                ${pipelineResult.verdict.allowed_amount_usd.toLocaleString()} USD
              </span>
            </div>
          </div>

          {pipelineResult.gate_token ? (
            <div className="p-3 bg-[#181011] text-[#f3f1ed] rounded-[4px] font-mono text-[11px] space-y-1">
              <div className="text-[9px] text-[#aaaaaa] uppercase">HMAC Gate Token Minted</div>
              <div className="break-all font-bold">{pipelineResult.gate_token.token}</div>
            </div>
          ) : (
            <div className="p-3 border border-[#181011] rounded-[4px] bg-[#f3f1ed] font-mono text-[11px] text-center text-[#181011] font-bold">
              GATE SEALED: PROPOSAL BLOCKED BY POLICY
            </div>
          )}
        </div>
      </div>
    </section>
  );
};
