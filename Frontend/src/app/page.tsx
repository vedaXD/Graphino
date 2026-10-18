"use client";

import React, { useState } from "react";
import { Header } from "@/components/Header";
import { HeroSection } from "@/components/HeroSection";
import { ProposalGateView } from "@/components/ProposalGateView";
import { ContagionEngineView } from "@/components/ContagionEngineView";
import { AgentBlackboardView } from "@/components/AgentBlackboardView";
import { TenantMemoryView } from "@/components/TenantMemoryView";
import { Footer } from "@/components/Footer";
import { DEFAULT_PROFILES } from "@/lib/memory/memoryStore";
import { UserProfile, PortfolioPosition } from "@/lib/types";
import { GRAPH_NODES } from "@/lib/data/graphData";

export default function Home() {
  const [profiles, setProfiles] = useState<UserProfile[]>(DEFAULT_PROFILES);
  const [currentProfile, setCurrentProfile] = useState<UserProfile>(DEFAULT_PROFILES[0]);
  const [activeWorkspaceView, setActiveWorkspaceView] = useState<
    "gate" | "contagion" | "blackboard" | "memory"
  >("gate");

  const handleSelectProfile = (profile: UserProfile) => {
    setCurrentProfile(profile);
  };

  const handleUpdateProfile = (updated: UserProfile) => {
    setCurrentProfile(updated);
    setProfiles((prev) =>
      prev.map((p) => (p.user_id === updated.user_id ? updated : p))
    );
  };

  const handleTradeExecuted = (
    protocolId: string,
    amountUsd: number,
    gateToken: string
  ) => {
    const protoNode = GRAPH_NODES.find((n) => n.id === protocolId);
    const newPosition: PortfolioPosition = {
      protocol_id: protocolId,
      name: protoNode?.name || protocolId,
      amount_usd: amountUsd,
      entered_at: "2024-10-18",
      gate_token: gateToken,
    };

    const updatedProfile: UserProfile = {
      ...currentProfile,
      positions: [newPosition, ...currentProfile.positions],
    };

    handleUpdateProfile(updatedProfile);
  };

  return (
    <div className="min-h-screen flex flex-col bg-[#f3f1ed] text-[#181011]">
      {/* Minimal Top Header */}
      <Header
        profiles={profiles}
        currentProfile={currentProfile}
        onSelectProfile={handleSelectProfile}
      />

      {/* Main Content Area */}
      <main className="flex-1">
        {/* Title Page (Hero Section: Only Title & Launch Button, Zero Fake Graphs) */}
        <HeroSection />

        {/* Real System Operations Section */}
        <div id="app" className="max-w-[1200px] mx-auto px-6 py-12 space-y-10 border-t border-[#d8d4d4] scroll-mt-16">
          {/* Workspace View Switcher */}
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-[#d8d4d4] pb-4">
            <div>
              <div className="text-[10px] font-mono uppercase tracking-[0.12em] text-[#aaaaaa]">
                FALKORDB ENGINE CONSOLE
              </div>
              <div className="text-[20px] font-normal text-[#181011]">
                {activeWorkspaceView === "gate" && "Deterministic Proposal Assessment & Action Gate"}
                {activeWorkspaceView === "contagion" && "Failure Contagion Shock Engine"}
                {activeWorkspaceView === "blackboard" && "Tri-Agent Orchestrator & Citation Validator"}
                {activeWorkspaceView === "memory" && "Tenant Memory & Graph-Off Benchmark"}
              </div>
            </div>

            {/* Clean Segmented Control */}
            <div className="flex flex-wrap items-center gap-1.5 bg-[#ffffff] p-1 rounded-[4px] border border-[#d8d4d4]">
              <button
                onClick={() => setActiveWorkspaceView("gate")}
                className={`px-3 py-1.5 rounded-[3px] text-[12px] font-mono transition-colors ${
                  activeWorkspaceView === "gate"
                    ? "bg-[#181011] text-[#ffffff]"
                    : "text-[#666666] hover:text-[#181011]"
                }`}
              >
                1. Proposal Gate
              </button>
              <button
                onClick={() => setActiveWorkspaceView("contagion")}
                className={`px-3 py-1.5 rounded-[3px] text-[12px] font-mono transition-colors ${
                  activeWorkspaceView === "contagion"
                    ? "bg-[#181011] text-[#ffffff]"
                    : "text-[#666666] hover:text-[#181011]"
                }`}
              >
                2. Contagion
              </button>
              <button
                onClick={() => setActiveWorkspaceView("blackboard")}
                className={`px-3 py-1.5 rounded-[3px] text-[12px] font-mono transition-colors ${
                  activeWorkspaceView === "blackboard"
                    ? "bg-[#181011] text-[#ffffff]"
                    : "text-[#666666] hover:text-[#181011]"
                }`}
              >
                3. Agents
              </button>
              <button
                onClick={() => setActiveWorkspaceView("memory")}
                className={`px-3 py-1.5 rounded-[3px] text-[12px] font-mono transition-colors ${
                  activeWorkspaceView === "memory"
                    ? "bg-[#181011] text-[#ffffff]"
                    : "text-[#666666] hover:text-[#181011]"
                }`}
              >
                4. Memory &amp; Benchmark
              </button>
            </div>
          </div>

          {/* Active Working Module */}
          <div className="pt-2">
            {activeWorkspaceView === "gate" && (
              <ProposalGateView
                userProfile={currentProfile}
                initialProtocolId="young-fork-protocol"
                onTradeExecuted={handleTradeExecuted}
              />
            )}

            {activeWorkspaceView === "contagion" && (
              <ContagionEngineView
                positions={currentProfile.positions}
                onAuditProtocol={() => setActiveWorkspaceView("gate")}
              />
            )}

            {activeWorkspaceView === "blackboard" && (
              <AgentBlackboardView userProfile={currentProfile} />
            )}

            {activeWorkspaceView === "memory" && (
              <TenantMemoryView
                currentProfile={currentProfile}
                onAuditProtocol={() => setActiveWorkspaceView("gate")}
              />
            )}
          </div>
        </div>
      </main>

      {/* Minimal Footer */}
      <Footer />
    </div>
  );
}
