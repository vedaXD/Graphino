"use client";

import React, { useState, useEffect, useRef } from "react";
import { AgentChatView } from "@/components/AgentChatView";
import { useTenant } from "@/lib/context/TenantContext";
import { UserProfile } from "@/lib/types";

interface FloatingAgentChatProps {
  userProfile?: UserProfile;
  onTradeExecuted?: (protocolId: string, amountUsd: number, gateToken: string) => void;
  onNavigateToVisualizer?: (protocolId: string) => void;
}

export const FloatingAgentChat: React.FC<FloatingAgentChatProps> = ({
  userProfile: propProfile,
  onTradeExecuted: propOnTradeExecuted,
  onNavigateToVisualizer,
}) => {
  const tenant = useTenant();
  const activeProfile = propProfile || tenant.currentProfile;
  const activeOnTrade = propOnTradeExecuted || tenant.executeTrade;

  const [isOpen, setIsOpen] = useState<boolean>(false);
  const chatRef = useRef<HTMLDivElement>(null);

  // Close on Escape key press
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape" && isOpen) {
        setIsOpen(false);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  return (
    <>
      {/* Floating Chat Trigger Button in Bottom-Right Corner */}
      <div className="fixed bottom-6 right-6 z-50">
        <button
          onClick={() => setIsOpen((prev) => !prev)}
          className={`flex items-center gap-2.5 px-4 h-12 rounded-full shadow-2xl transition-all duration-200 cursor-pointer border ${
            isOpen
              ? "bg-[#2c2224] text-white border-[#4d3a3d] scale-95"
              : "bg-[#181011] hover:bg-[#282022] text-white border-[#383032] hover:scale-105 active:scale-95"
          }`}
          title={isOpen ? "Minimize AI Agent Chat (Esc)" : "Open AI Agent Chat with FalkorDB & Gemini"}
          aria-label="Toggle Bulwark AI Agent Chat"
        >
          {isOpen ? (
            <>
              <span className="text-[13px] font-mono font-bold">✕</span>
              <span className="text-[12px] font-mono tracking-wide font-medium">Close</span>
            </>
          ) : (
            <>
              {/* Glowing Pulse Dot */}
              <div className="relative flex items-center justify-center">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
                <span className="absolute w-4 h-4 rounded-full bg-emerald-400 opacity-40 animate-ping"></span>
              </div>
              <span className="text-[14px]">🤖</span>
              <span className="text-[12px] font-mono tracking-wide font-bold">
                AI Agent
              </span>
            </>
          )}
        </button>
      </div>

      {/* Floating Chat Modal Window */}
      {isOpen && (
        <div
          ref={chatRef}
          className="fixed bottom-21 right-6 z-50 w-[490px] max-w-[calc(100vw-2rem)] h-[650px] max-h-[calc(100vh-6.5rem)] bg-[#ffffff] rounded-2xl shadow-2xl border border-[#d8d4d4] flex flex-col overflow-hidden animate-in fade-in slide-in-from-bottom-5 duration-200"
          role="dialog"
          aria-label="Bulwark AI Risk Agent Interface"
        >
          {/* Header Bar */}
          <div className="flex items-center justify-between px-4 py-3 bg-[#181011] text-white shrink-0">
            <div className="flex items-center gap-2.5">
              <div className="w-7 h-7 rounded-lg bg-[#ffffff]/10 flex items-center justify-center text-sm">
                🤖
              </div>
              <div>
                <div className="flex items-center gap-2">
                  <h3 className="text-[13px] font-bold font-mono tracking-tight text-white leading-none">
                    Bulwark AI Agent
                  </h3>
                  <span className="text-[9px] bg-emerald-500/20 text-emerald-300 border border-emerald-400/30 px-1.5 py-0.2 rounded font-mono">
                    LIVE
                  </span>
                </div>
                <p className="text-[10px] font-mono text-[#aaaaaa] mt-0.5">
                  FalkorDB GraphBLAS • Gemini 3.5 Flash
                </p>
              </div>
            </div>

            {/* Action Button: Close */}
            <div className="flex items-center gap-1">
              <button
                onClick={() => setIsOpen(false)}
                className="w-7 h-7 flex items-center justify-center text-[#aaaaaa] hover:text-white rounded hover:bg-white/10 transition-colors text-xs font-bold font-mono cursor-pointer"
                title="Close Window (Esc)"
              >
                ✕
              </button>
            </div>
          </div>

          {/* Embedded Agent Chat View */}
          <div className="flex-1 min-h-0">
            <AgentChatView
              isFloating={true}
              userProfile={activeProfile}
              onTradeExecuted={activeOnTrade}
              onNavigateToVisualizer={onNavigateToVisualizer}
            />
          </div>
        </div>
      )}
    </>
  );
};
