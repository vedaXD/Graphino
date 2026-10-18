import React from "react";
import { UserProfile } from "@/lib/types";
import { GraphOffBenchmarkView } from "./GraphOffBenchmarkView";
import { UserMemoryGraphVisualizer } from "./UserMemoryGraphVisualizer";

interface TenantMemoryViewProps {
  currentProfile: UserProfile;
  onAuditProtocol: (protocolId: string) => void;
}

export const TenantMemoryView: React.FC<TenantMemoryViewProps> = ({
  currentProfile,
  onAuditProtocol,
}) => {
  return (
    <section id="memory" className="space-y-8 pt-4 scroll-mt-20">
      {/* Live FalkorDB Tenant Memory Graph Visualizer */}
      <UserMemoryGraphVisualizer
        currentProfile={currentProfile}
        onAuditProtocol={onAuditProtocol}
      />

      {/* Grid: Left Tenant Memory Rules & Mistakes / Right Benchmark Comparison */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        {/* Left Column: Procedural Rules & Mistakes (6 cols) */}
        <div className="lg:col-span-6 space-y-6">
          {/* Procedural Rules */}
          <div className="surface-white p-5 space-y-3">
            <div className="flex items-center justify-between border-b border-[#d8d4d4] pb-2">
              <span className="tracked-badge text-[9px]">LEARNED PROCEDURAL RULES (R7)</span>
              <span className="text-[11px] font-mono text-[#666666]">
                {currentProfile.memory_rules.length} Active Rules
              </span>
            </div>

            <div className="space-y-2.5 font-mono text-[12px]">
              {currentProfile.memory_rules.map((rule) => (
                <div key={rule.id} className="p-3 bg-[#f3f1ed] rounded-[4px] border border-[#d8d4d4] space-y-1">
                  <div className="flex justify-between items-center text-[10px] text-[#aaaaaa]">
                    <span>{rule.id} · TAG: {rule.tag}</span>
                    <span className="tracked-badge text-[8px] py-0">{rule.action.toUpperCase()}</span>
                  </div>
                  <p className="text-[#181011] font-sans text-[13px]">{rule.note}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Past Mistake Immunity Journal */}
          <div className="surface-white p-5 space-y-3">
            <div className="flex items-center justify-between border-b border-[#d8d4d4] pb-2">
              <span className="tracked-badge text-[9px]">HISTORICAL LOSS JOURNAL</span>
              <span className="text-[11px] font-mono text-[#666666]">
                {currentProfile.mistakes.length} Recorded Losses
              </span>
            </div>

            <div className="space-y-2 font-mono text-[11px]">
              {currentProfile.mistakes.map((m) => (
                <div key={m.id} className="p-2.5 bg-[#f3f1ed] rounded-[4px] border border-[#d8d4d4] space-y-0.5">
                  <div className="flex justify-between font-bold text-[#181011]">
                    <span>{m.protocol_involved}</span>
                    <span className="text-[#302023]">-${m.loss_usd.toLocaleString()} USD</span>
                  </div>
                  <p className="text-[#666666] font-sans text-[12px]">{m.summary}</p>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right Column: Embedded Graph-Off Benchmark Comparison (6 cols) */}
        <div className="lg:col-span-6">
          <GraphOffBenchmarkView userProfile={currentProfile} />
        </div>
      </div>
    </section>
  );
};
