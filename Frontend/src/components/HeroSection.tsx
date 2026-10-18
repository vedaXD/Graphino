import React from "react";

interface HeroSectionProps {
  onLaunch?: () => void;
}

export const HeroSection: React.FC<HeroSectionProps> = ({ onLaunch }) => {
  return (
    <section className="min-h-[82vh] flex flex-col justify-center items-center text-center px-6 max-w-[1100px] mx-auto py-20">
      <div className="space-y-8 max-w-[880px] flex flex-col items-center">
        {/* Minimal Uppercase Tag */}
        <div className="inline-flex items-center gap-2">
          <span className="tracked-badge text-[10px] tracking-[0.14em]">
            BULWARK · FALKORDB
          </span>
        </div>

        {/* Minimal Title */}
        <h1 className="text-[44px] sm:text-[62px] md:text-[72px] font-normal leading-[1.08] text-[#181011] tracking-[-0.03em]">
          Building the relational intelligence layer for{" "}
          <span className="highlight-animated font-bold text-[#181011]">
            decentralized capital.
          </span>
        </h1>

        {/* Launch Button Only */}
        <div className="pt-4">
          <a
            href="#app"
            onClick={onLaunch}
            className="pill-cta text-[16px] py-3 px-8 font-normal hover:scale-[1.02] transition-transform"
          >
            <span>Launch</span>
            <span className="text-[14px] opacity-70">→</span>
          </a>
        </div>
      </div>
    </section>
  );
};
