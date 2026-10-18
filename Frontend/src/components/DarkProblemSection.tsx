import React from "react";
import { DiamondGrid } from "./DiamondGrid";

export const DarkProblemSection: React.FC = () => {
  const problems = [
    {
      title: "Shared Downstream Oracles",
      summary:
        "Protocols appear isolated on surface TVL tables, but quietly share the same price feeds and node validators. Failure at depth wipes out multi-asset portfolios.",
    },
    {
      title: "Single-Key Admin Backdoors",
      summary:
        "Millions in capital governed by 1-of-1 private EOA keys with zero timelock delay, masquerading as decentralized smart contracts.",
    },
    {
      title: "Repeated Historical Exploits",
      summary:
        "Without persistent, tenant-isolated memory, allocators repeat identical loss patterns across forked protocols within weeks.",
    },
  ];

  return (
    <section className="w-full bg-[#302023] text-[#ffffff] py-16 px-6 border-y border-[#181011]">
      <div className="max-w-[1240px] mx-auto space-y-10">
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="bg-[#ffffff] text-[#181011] rounded-[4px] px-2 py-0.5 text-[10px] font-mono tracking-[0.10em] uppercase">
              THE RELATIONAL THREAT
            </span>
          </div>

          <h2 className="text-[28px] sm:text-[36px] font-normal text-[#ffffff] tracking-[-0.02em] max-w-[700px]">
            Where isolated audits fail, connected graphs protect.
          </h2>
        </div>

        {/* 3 Minimal Problem Columns */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
          {problems.map((p, idx) => (
            <div
              key={idx}
              className="pt-5 border-t border-[#ffffff]/20 space-y-3"
            >
              <div className="flex items-center gap-2">
                <DiamondGrid matrix={3} size={6} color="white" />
                <span className="text-[11px] font-mono text-[#aaaaaa]">
                  0{idx + 1}
                </span>
              </div>
              <h3 className="text-[17px] font-bold text-[#ffffff]">{p.title}</h3>
              <p className="text-[13px] text-[#aaaaaa] leading-[1.5]">
                {p.summary}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};
