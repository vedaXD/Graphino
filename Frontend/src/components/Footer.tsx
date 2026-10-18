import React from "react";
import { DiamondGrid } from "./DiamondGrid";

export const Footer: React.FC = () => {
  return (
    <footer className="w-full bg-[#f3f1ed] border-t border-[#d8d4d4] py-12 px-6 mt-20 text-[#666666]">
      <div className="max-w-[1280px] mx-auto space-y-8">
        <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-6 border-b border-[#d8d4d4] pb-8">
          <div className="flex items-center gap-3">
            <DiamondGrid matrix={3} size={7} color="ink" />
            <div>
              <span className="text-[15px] font-normal text-[#181011]">
                Bulwark Systemic Guardian
              </span>
              <span className="block text-[11px] font-mono text-[#aaaaaa]">
                ENGINEERING DOSSIER · FALKORDB GRAPH DATABASE
              </span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-6 text-[13px] font-mono">
            <span className="text-[#181011]">Track 1: Connected Data</span>
            <span className="text-[#aaaaaa]">·</span>
            <span className="text-[#181011]">Track 2: Agent Memory &amp; Coordination</span>
            <span className="text-[#aaaaaa]">·</span>
            <span className="tracked-badge text-[10px]">v2.4 INSTITUTIONAL</span>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 text-[12px] leading-[1.5]">
          <div>
            <div className="text-[11px] font-mono uppercase tracking-[0.10em] text-[#aaaaaa] mb-1">
              Data Attribution
            </div>
            <p>
              Protocol TVL, multi-chain circulation, pools, and incident data are sourced from public DeFiLlama APIs and official smart contract documentation.
            </p>
          </div>

          <div>
            <div className="text-[11px] font-mono uppercase tracking-[0.10em] text-[#aaaaaa] mb-1">
              Deterministic Guarantees
            </div>
            <p>
              Risk verdicts derive strictly from deterministic graph traversals over verified, risk-eligible edges. The language model never decides verdicts.
            </p>
          </div>

          <div>
            <div className="text-[11px] font-mono uppercase tracking-[0.10em] text-[#aaaaaa] mb-1">
              Notice
            </div>
            <p>
              Autonomous paper allocation and risk research guardian. Non-custodial, paper execution only. Not financial or trading advice.
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
};
