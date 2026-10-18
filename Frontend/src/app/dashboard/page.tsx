"use client";

import React, { useState } from "react";
import Link from "next/link";
import { ProposalGateView } from "@/components/ProposalGateView";
import { ContagionEngineView } from "@/components/ContagionEngineView";
import { AgentBlackboardView } from "@/components/AgentBlackboardView";
import { TenantMemoryView } from "@/components/TenantMemoryView";
import { GraphVisualizerView } from "@/components/GraphVisualizerView";
import { Footer } from "@/components/Footer";
import { useTenant } from "@/lib/context/TenantContext";

const NAVIGATION_TABS = [
  { id: "visualizer", label: "Graph Visualizer" },
  { id: "gate", label: "Proposal Gate" },
  { id: "contagion", label: "Contagion" },
  { id: "blackboard", label: "Agents" },
  { id: "memory", label: "Memory & Benchmark" },
] as const;

type WorkspaceTabId = (typeof NAVIGATION_TABS)[number]["id"];

export default function DashboardPage() {
  const {
    profiles,
    currentProfile,
    selectProfileById,
    executeTrade,
    totalPortfolioUsd,
  } = useTenant();

  const [activeWorkspaceView, setActiveWorkspaceView] =
    useState<WorkspaceTabId>("visualizer");
  const [selectedAuditProtocol, setSelectedAuditProtocol] =
    useState<string>("aave-v3");
  const [selectedShockNode, setSelectedShockNode] =
    useState<string>("chainlink-price-feeds");

  return (
    <div className="min-h-screen flex flex-col bg-[#f3f1ed] text-[#181011]">
      {/* Clean, Properly Spaced, Professional Navigation Header */}
      <header className="sticky top-0 z-40 bg-[#ffffff] border-b border-[#e7e5e0] shadow-[0_1px_3px_rgba(0,0,0,0.03)]">
        <div className="max-w-[1480px] mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between gap-4 md:gap-8">
          
          {/* Left: Brand Identity + Live FalkorDB Cluster Indicator */}
          <div className="flex items-center gap-3.5 shrink-0">
            <Link
              href="/"
              className="flex items-center gap-2.5 group"
              title="Return to Home"
            >
              <div className="w-3 h-3 bg-[#181011] rotate-45 transform group-hover:rotate-90 transition-transform duration-300" />
              <span className="text-[16px] font-bold tracking-tight text-[#181011]">
                Bulwark
              </span>
            </Link>

            <span className="h-4 w-px bg-[#e0deda]" />

            <div className="hidden sm:flex items-center gap-2 px-2.5 py-1 rounded-full bg-emerald-50 border border-emerald-200/90 text-[11px] font-mono text-emerald-800">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              <span className="font-semibold tracking-wide">FALKORDB</span>
              <span className="text-emerald-400 font-sans">•</span>
              <span className="text-emerald-700/80 font-normal">:6379</span>
            </div>
          </div>

          {/* Center: Clean Segmented Workspace Navigation Tabs (No Numbers) */}
          <nav className="flex items-center overflow-x-auto scrollbar-none py-1">
            <div className="flex items-center gap-1.5 p-1 bg-[#f5f4f0] rounded-lg border border-[#e5e3dc] shadow-2xs">
              {NAVIGATION_TABS.map((tab) => {
                const isActive = activeWorkspaceView === tab.id;
                return (
                  <button
                    key={tab.id}
                    onClick={() => setActiveWorkspaceView(tab.id)}
                    className={`px-3.5 py-1.5 rounded-md text-[12px] font-mono whitespace-nowrap transition-all duration-150 cursor-pointer ${
                      isActive
                        ? "bg-[#181011] text-[#ffffff] font-bold shadow-xs"
                        : "text-[#555555] hover:text-[#181011] hover:bg-[#eae8e3]/80 font-medium"
                    }`}
                  >
                    {tab.label}
                  </button>
                );
              })}
            </div>
          </nav>

          {/* Right: Portfolio Metric Chip + Tenant Switcher + Home Navigation */}
          <div className="flex items-center gap-3 shrink-0">
            <div className="hidden lg:flex items-center gap-2 px-3 py-1.5 bg-[#fbfbfa] border border-[#e7e5e0] rounded-lg text-[12px]">
              <span className="text-[10px] font-mono font-medium text-[#888888] tracking-wider uppercase">
                PORTFOLIO
              </span>
              <span className="font-mono font-bold text-emerald-700">
                ${totalPortfolioUsd.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="hidden xl:inline text-[10px] font-mono text-[#888888] uppercase tracking-wider font-semibold">
                TENANT:
              </span>
              <select
                value={currentProfile.user_id}
                onChange={(e) => selectProfileById(e.target.value)}
                className="bg-[#ffffff] border border-[#e7e5e0] hover:border-[#181011] text-[#181011] text-[12px] font-mono px-3 py-1.5 rounded-lg focus:outline-none focus:ring-1 focus:ring-[#181011] cursor-pointer transition-colors shadow-2xs"
              >
                {profiles.map((p) => (
                  <option key={p.user_id} value={p.user_id}>
                    {p.display_name}
                  </option>
                ))}
              </select>
            </div>

            <Link
              href="/"
              className="px-3 py-1.5 rounded-lg border border-[#e7e5e0] hover:border-[#181011] text-[12px] font-mono text-[#555555] hover:text-[#181011] bg-[#ffffff] hover:bg-[#fbfbfa] transition-colors flex items-center gap-1.5 shadow-2xs"
              title="Return to Home Landing Page"
            >
              <span>←</span>
              <span>Home</span>
            </Link>
          </div>
        </div>
      </header>

      {/* Main Dashboard Workspace Content */}
      <main className="flex-1 max-w-[1480px] w-full mx-auto px-4 sm:px-6 lg:px-8 py-6">
        {activeWorkspaceView === "visualizer" && (
          <GraphVisualizerView
            onAuditProtocol={(protocolId) => {
              setSelectedAuditProtocol(protocolId);
              setActiveWorkspaceView("gate");
            }}
            onSimulateShock={(nodeId) => {
              setSelectedShockNode(nodeId);
              setActiveWorkspaceView("contagion");
            }}
          />
        )}

        {activeWorkspaceView === "gate" && (
          <ProposalGateView
            userProfile={currentProfile}
            initialProtocolId={selectedAuditProtocol}
            onTradeExecuted={executeTrade}
          />
        )}

        {activeWorkspaceView === "contagion" && (
          <ContagionEngineView
            positions={currentProfile.positions}
            initialTargetNodeId={selectedShockNode}
            onAuditProtocol={(protocolId) => {
              setSelectedAuditProtocol(protocolId);
              setActiveWorkspaceView("gate");
            }}
          />
        )}

        {activeWorkspaceView === "blackboard" && (
          <AgentBlackboardView userProfile={currentProfile} />
        )}

        {activeWorkspaceView === "memory" && (
          <TenantMemoryView
            currentProfile={currentProfile}
            onAuditProtocol={(protocolId) => {
              setSelectedAuditProtocol(protocolId);
              setActiveWorkspaceView("gate");
            }}
          />
        )}
      </main>

      <Footer />
    </div>
  );
}
