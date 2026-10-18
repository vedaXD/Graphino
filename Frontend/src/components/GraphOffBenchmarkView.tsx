import React, { useState } from "react";
import { runAgentPipeline } from "@/lib/agents/orchestrator";
import { UserProfile } from "@/lib/types";

interface GraphOffBenchmarkViewProps {
  userProfile: UserProfile;
}

export const GraphOffBenchmarkView: React.FC<GraphOffBenchmarkViewProps> = ({
  userProfile,
}) => {
  const [selectedCase, setSelectedCase] = useState<"young-fork" | "algo-stable">("young-fork");

  const testCases = {
    "young-fork": {
      protocol_id: "young-fork-protocol",
      name: "Apex Lend (Young Fork)",
      amount_usd: 100000,
      description: "1-of-1 private EOA key with 0h timelock and 0 audits.",
    },
    "algo-stable": {
      protocol_id: "algo-cash-protocol",
      name: "Matrix CDP (Algorithmic Peg)",
      amount_usd: 150000,
      description: "Uncollateralized algorithmic stablecoin backing.",
    },
  };

  const currentCase = testCases[selectedCase];

  // Run Graph-On
  const graphOnResult = runAgentPipeline(
    { protocol_id: currentCase.protocol_id, amount_usd: currentCase.amount_usd },
    userProfile,
    false
  );

  return (
    <div className="surface-white p-5 space-y-4">
      {/* Benchmark Header & Scenario Toggle */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 border-b border-[#d8d4d4] pb-3">
        <div>
          <span className="tracked-badge text-[9px]">GRAPH-OFF BENCHMARK</span>
          <div className="font-bold text-[14px] text-[#181011] mt-0.5">
            Why FalkorDB Is Indispensable
          </div>
        </div>

        <div className="flex gap-1.5 font-mono text-[11px]">
          {(["young-fork", "algo-stable"] as const).map((k) => (
            <button
              key={k}
              onClick={() => setSelectedCase(k)}
              className={`px-2.5 py-1 rounded-[4px] border ${
                selectedCase === k
                  ? "bg-[#181011] text-[#ffffff] border-[#181011]"
                  : "bg-[#ffffff] text-[#181011] border-[#d8d4d4]"
              }`}
            >
              {k === "young-fork" ? "Admin Key Backdoor" : "Algo Stablecoin"}
            </button>
          ))}
        </div>
      </div>

      {/* Side-by-Side Comparison */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 text-[11px] font-mono">
        {/* Left: Ungrounded LLM */}
        <div className="p-3.5 bg-[#f3f1ed] rounded-[4px] border border-[#d8d4d4] space-y-2">
          <div className="flex justify-between items-center text-[10px]">
            <span className="text-[#aaaaaa] uppercase font-bold">STANDARD MODEL (GRAPH-OFF)</span>
            <span className="text-[#181011] font-bold border border-[#181011] px-1.5 py-0.2 rounded-[2px]">
              FALSE ALLOW
            </span>
          </div>
          <p className="text-[#666666] leading-[1.4] font-sans text-[12px]">
            &quot;{currentCase.name} appears active and functional with high APY incentives. Public documentation does not mention critical exploits. Recommended for allocation.&quot;
          </p>
          <div className="pt-2 border-t border-[#d8d4d4] text-[#181011] text-[10px] space-y-0.5">
            <div>✕ Missed 1-of-1 admin EOA private key</div>
            <div>✕ Ignored 0 listed audits and 34d age</div>
            <div>✕ Zero memory of past $240k loss</div>
          </div>
        </div>

        {/* Right: Bulwark Graph-On */}
        <div className="p-3.5 bg-[#ffffff] rounded-[4px] border-2 border-[#181011] space-y-2">
          <div className="flex justify-between items-center text-[10px]">
            <span className="text-[#181011] uppercase font-bold">BULWARK (GRAPH-ON)</span>
            <span className="bg-[#181011] text-[#ffffff] font-bold px-1.5 py-0.2 rounded-[2px]">
              {graphOnResult.verdict.outcome}
            </span>
          </div>
          <div className="space-y-1 font-sans text-[12px] text-[#181011]">
            <p className="font-bold">Deterministic Graph Protections:</p>
            <ul className="list-disc pl-3 text-[11px] font-mono text-[#333333] space-y-0.5">
              {graphOnResult.verdict.findings.slice(0, 3).map((f) => (
                <li key={f.id}>
                  {f.rule}: {f.action.toUpperCase()} ({f.subject})
                </li>
              ))}
            </ul>
          </div>
          <div className="pt-2 border-t border-[#d8d4d4] text-[#181011] text-[10px] space-y-0.5">
            <div>✓ Enforced Rule R5 (single EOA deployer)</div>
            <div>✓ Applied Rule R7 memory immunity</div>
            <div>✓ HMAC action gate refused entry</div>
          </div>
        </div>
      </div>
    </div>
  );
};
