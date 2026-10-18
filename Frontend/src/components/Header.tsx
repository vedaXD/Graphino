import React from "react";
import { UserProfile } from "@/lib/types";

interface HeaderProps {
  profiles: UserProfile[];
  currentProfile: UserProfile;
  onSelectProfile: (profile: UserProfile) => void;
}

export const Header: React.FC<HeaderProps> = ({
  profiles,
  currentProfile,
  onSelectProfile,
}) => {
  return (
    <header className="sticky top-0 z-50 bg-[#f3f1ed]/95 backdrop-blur-sm border-b border-[#d8d4d4] transition-all">
      <div className="max-w-[1200px] mx-auto px-6 h-16 flex items-center justify-between gap-4">
        {/* Brand */}
        <a href="#" className="flex items-center gap-2.5 group">
          <div className="w-2.5 h-2.5 bg-[#181011] rotate-45 transform group-hover:rotate-90 transition-transform duration-300" />
          <span className="text-[15px] font-normal tracking-[-0.01em] text-[#181011]">
            Bulwark
          </span>
          <span className="text-[#aaaaaa] text-xs">/</span>
          <span className="text-[11px] font-mono text-[#666666]">
            FalkorDB
          </span>
        </a>

        {/* Tenant Switcher & Launch Button */}
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2 text-xs">
            <span className="hidden sm:inline text-[#aaaaaa] text-[10px] uppercase tracking-[0.10em] font-mono">
              TENANT:
            </span>
            <select
              value={currentProfile.user_id}
              onChange={(e) => {
                const found = profiles.find((p) => p.user_id === e.target.value);
                if (found) onSelectProfile(found);
              }}
              className="bg-[#ffffff] border border-[#d8d4d4] text-[#181011] text-[12px] px-2.5 py-1 rounded-[4px] focus:outline-none focus:border-[#181011] font-mono cursor-pointer"
            >
              {profiles.map((p) => (
                <option key={p.user_id} value={p.user_id}>
                  {p.display_name}
                </option>
              ))}
            </select>
          </div>

          <a href="#app" className="pill-cta text-[13px] py-1.5 px-4 font-normal">
            <span>Launch</span>
            <span className="text-[11px] opacity-60">↓</span>
          </a>
        </div>
      </div>
    </header>
  );
};
