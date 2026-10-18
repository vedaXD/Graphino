import React from "react";
import Link from "next/link";

interface HeroSectionProps {
  onLaunch?: () => void;
}

export const HeroSection: React.FC<HeroSectionProps> = ({ onLaunch }) => {
  return (
    <section className="flex flex-col justify-center items-center text-center px-6 max-w-[1100px] mx-auto py-16 sm:py-24">
      <div className="space-y-6 max-w-[880px] flex flex-col items-center">
        {/* Minimal Uppercase Tag */}
        <div className="inline-flex items-center gap-2">
          <span className="tracked-badge text-[10px] tracking-[0.14em]">
            BULWARK · FALKORDB GRAPHBLAS
          </span>
          <span className="text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200 px-2 py-0.5 rounded font-mono">
            LIVE ENGINE
          </span>
        </div>

        {/* Minimal Title */}
        <h1 className="text-[40px] sm:text-[56px] md:text-[68px] font-normal leading-[1.1] text-[#181011] tracking-[-0.03em]">
          Building the relational intelligence layer for{" "}
          <span className="highlight-animated font-bold text-[#181011]">
            decentralized capital.
          </span>
        </h1>

        {/* Subtitle */}
        <p className="text-[16px] sm:text-[18px] text-[#666666] max-w-[640px] font-sans leading-relaxed">
          Deterministic HMAC action gates, multi-hop dependency intelligence, and tenant-isolated episodic memory powered by FalkorDB GraphBLAS.
        </p>

        {/* Launch Button to Dedicated Dashboard */}
        <div className="pt-2 flex items-center justify-center">
          <Link
            href="/dashboard"
            onClick={onLaunch}
            className="pill-cta text-[15px] py-3 px-8 font-normal hover:scale-[1.02] transition-transform flex items-center gap-2 shadow-xs"
          >
            <span>Launch Console Dashboard</span>
            <span className="text-[14px] opacity-70">→</span>
          </Link>
        </div>
      </div>

      {/* 3 Clean Key Invariants Highlights */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 pt-16 w-full max-w-[960px] text-left">
        <div className="p-5 rounded-[4px] border border-[#d8d4d4] bg-[#ffffff] space-y-2">
          <span className="text-[10px] font-mono text-[#888888] uppercase tracking-wider block">
            01 / DETERMINISTIC ACTION GATE
          </span>
          <h3 className="text-[16px] font-bold text-[#181011]">
            Cryptographic HMAC Tokens
          </h3>
          <p className="text-[12px] text-[#666666] leading-relaxed">
            LLMs never decide trading verdicts. Hard rules run deterministically on FalkorDB graph facts, issuing cryptographic HMAC tokens for execution.
          </p>
        </div>

        <div className="p-5 rounded-[4px] border border-[#d8d4d4] bg-[#ffffff] space-y-2">
          <span className="text-[10px] font-mono text-[#888888] uppercase tracking-wider block">
            02 / MULTI-HOP GRAPHBLAS
          </span>
          <h3 className="text-[16px] font-bold text-[#181011]">
            Deep Dependency Intelligence
          </h3>
          <p className="text-[12px] text-[#666666] leading-relaxed">
            Traverses up to 4 hops in &lt;1.2ms across protocols, oracle price feeds, and governance timelocks to detect single points of failure.
          </p>
        </div>

        <div className="p-5 rounded-[4px] border border-[#d8d4d4] bg-[#ffffff] space-y-2">
          <span className="text-[10px] font-mono text-[#888888] uppercase tracking-wider block">
            03 / TENANT MEMORY
          </span>
          <h3 className="text-[16px] font-bold text-[#181011]">
            mem_&lt;user_id&gt; Isolation
          </h3>
          <p className="text-[12px] text-[#666666] leading-relaxed">
            Each user operates in an isolated memory graph tracking active positions, learned procedural rules, and historical mistake immunity.
          </p>
        </div>
      </div>
    </section>
  );
};
