"use client";

import React, { useState, useRef, useEffect } from "react";
import { runAgentPipeline, PipelineResult } from "@/lib/agents/orchestrator";
import { GRAPH_NODES } from "@/lib/data/graphData";
import { UserProfile, Proposal } from "@/lib/types";

interface AgentChatViewProps {
  userProfile: UserProfile;
  onTradeExecuted?: (protocolId: string, amountUsd: number, gateToken: string) => void;
  onNavigateToVisualizer?: (protocolId: string) => void;
  isFloating?: boolean;
}

interface ChatMessage {
  id: string;
  sender: "user" | "agent";
  text: string;
  timestamp: string;
  explanation?: string;
  task_id?: string;
  proposal?: Proposal;
  outcome?: string;
  allowed_amount_usd?: number;
  findings?: Array<{ id?: string; rule?: string; severity?: string; summary?: string; action?: string; evidence?: any[] }>;
  gate_token?: string | null;
  tradeExecuted?: boolean;
  graphOff?: boolean;
  abstention_active?: boolean;
  isLiveFalkorDB?: boolean;
}

const FormattedMessage: React.FC<{ content: string; isUser: boolean }> = ({ content, isUser }) => {
  if (isUser) {
    return <div className="text-[13px] leading-relaxed font-sans">{content}</div>;
  }

  const lines = content.split("\n");
  const elements: React.ReactNode[] = [];

  let inList = false;
  let listItems: React.ReactNode[] = [];
  let tableRows: string[][] = [];
  let inTable = false;

  const flushList = (keyPrefix: string) => {
    if (inList && listItems.length > 0) {
      elements.push(
        <ul key={`ul-${keyPrefix}`} className="space-y-1 my-2 pl-1">
          {listItems}
        </ul>
      );
      listItems = [];
      inList = false;
    }
  };

  const flushTable = (keyPrefix: string) => {
    if (inTable && tableRows.length > 0) {
      const headerRow = tableRows[0];
      const bodyRows = tableRows.slice(1);
      elements.push(
        <div key={`table-${keyPrefix}`} className="overflow-x-auto my-2.5 border border-[#e5e5e5] rounded-md">
          <table className="min-w-full divide-y divide-[#e5e5e5] text-[11px]">
            <thead className="bg-[#f9f8f6]">
              <tr>
                {headerRow.map((cell, cIdx) => (
                  <th key={cIdx} className="px-3 py-1.5 font-mono font-bold text-[#181011] tracking-wider uppercase">
                    {parseInline(cell)}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-[#ece9e6] bg-white">
              {bodyRows.map((row, rIdx) => (
                <tr key={rIdx} className="hover:bg-[#faf9f7] transition-colors">
                  {row.map((cell, cIdx) => (
                    <td key={cIdx} className="px-3 py-1.5 text-[#333333] whitespace-nowrap">
                      {parseInline(cell)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
      tableRows = [];
      inTable = false;
    }
  };

  const parseInline = (text: string) => {
    const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
    return parts.map((part, i) => {
      if (part.startsWith("**") && part.endsWith("**")) {
        return <strong key={i} className="font-bold text-[#181011]">{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith("`") && part.endsWith("`")) {
        return (
          <code key={i} className="px-1.5 py-0.5 rounded bg-[#f3f1ed] text-[#181011] text-[11px] font-mono border border-[#d8d4d4]">
            {part.slice(1, -1)}
          </code>
        );
      }
      return part;
    });
  };

  lines.forEach((rawLine, idx) => {
    const line = rawLine.trim();

    if (!line) {
      flushList(`empty-${idx}`);
      flushTable(`empty-${idx}`);
      return;
    }

    // Markdown Table Row
    if (line.startsWith("|") && line.endsWith("|")) {
      flushList(`table-start-${idx}`);
      // Skip separator row like | :--- | :--- |
      if (/^\|(\s*[:-]+[-|\s]*)\|$/.test(line)) {
        return;
      }
      const cells = line
        .slice(1, -1)
        .split("|")
        .map((c) => c.trim());
      inTable = true;
      tableRows.push(cells);
      return;
    } else {
      flushTable(`non-table-${idx}`);
    }

    // Divider
    if (line === "---" || line === "***") {
      flushList(`hr-${idx}`);
      elements.push(<hr key={`hr-${idx}`} className="my-2.5 border-[#e5e5e5]" />);
      return;
    }

    if (line.startsWith("### ")) {
      flushList(`h3-${idx}`);
      elements.push(
        <h4 key={`h3-${idx}`} className="text-[13px] font-bold text-[#181011] mt-3 mb-1 border-b border-[#e5e5e5] pb-1 uppercase tracking-wider font-mono">
          {parseInline(line.slice(4))}
        </h4>
      );
      return;
    }
    if (line.startsWith("## ")) {
      flushList(`h2-${idx}`);
      elements.push(
        <h3 key={`h2-${idx}`} className="text-[15px] font-bold text-[#181011] mt-3.5 mb-1.5">
          {parseInline(line.slice(3))}
        </h3>
      );
      return;
    }

    if (line.startsWith("> ")) {
      flushList(`quote-${idx}`);
      elements.push(
        <div key={`quote-${idx}`} className="my-2 p-2.5 rounded bg-amber-50/90 border-l-3 border-amber-500 text-[11px] text-amber-900 font-mono">
          {parseInline(line.slice(2))}
        </div>
      );
      return;
    }

    if (line.startsWith("* ") || line.startsWith("- ")) {
      inList = true;
      listItems.push(
        <li key={`li-${idx}`} className="flex items-start gap-2 text-[12px] leading-relaxed text-[#222222]">
          <span className="text-[#888888] mt-1 text-[8px]">●</span>
          <span className="flex-1">{parseInline(line.slice(2))}</span>
        </li>
      );
      return;
    }

    const numMatch = line.match(/^(\d+)\.\s+(.*)/);
    if (numMatch) {
      flushList(`num-${idx}`);
      elements.push(
        <div key={`num-${idx}`} className="flex items-start gap-2 text-[12px] my-1 leading-relaxed text-[#222222]">
          <span className="font-mono text-[11px] font-bold text-[#666666] min-w-4">{numMatch[1]}.</span>
          <span className="flex-1">{parseInline(numMatch[2])}</span>
        </div>
      );
      return;
    }

    flushList(`p-${idx}`);
    elements.push(
      <p key={`p-${idx}`} className="text-[12px] leading-relaxed text-[#222222] my-1">
        {parseInline(line)}
      </p>
    );
  });

  flushList("final");
  flushTable("final");
  return <div className="space-y-1 font-sans">{elements}</div>;
};

export const AgentChatView: React.FC<AgentChatViewProps> = ({
  userProfile,
  onTradeExecuted = () => {},
  onNavigateToVisualizer = () => {},
  isFloating = false,
}) => {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "msg-welcome",
      sender: "agent",
      text: `Hello! I am your Bulwark Autonomous Risk & Investment Agent. I am connected to FalkorDB (\`defi_risk\`, \`defi_evidence\`, and \`mem_${userProfile.user_id}\`).

Every query you submit triggers a real multi-hop graph traversal and epistemic verification. Try asking to evaluate an investment in any DeFi protocol.`,
      timestamp: "Just now",
      isLiveFalkorDB: true,
    },
  ]);

  const [inputText, setInputText] = useState<string>("");
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [currentStepIndex, setCurrentStepIndex] = useState<number>(0);
  const [graphOffMode, setGraphOffMode] = useState<boolean>(false);
  const [expandedTraceId, setExpandedTraceId] = useState<string | null>(null);

  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isProcessing, currentStepIndex]);

  const handleSendMessage = async (textToSend?: string) => {
    const query = textToSend || inputText;
    if (!query.trim() || isProcessing) return;

    const userMsgId = `user-${Date.now()}`;
    const userMessage: ChatMessage = {
      id: userMsgId,
      sender: "user",
      text: query,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputText("");
    setIsProcessing(true);
    setCurrentStepIndex(1);

    // Live stepper indicators
    const stepTimer1 = setTimeout(() => setCurrentStepIndex(2), 350);
    const stepTimer2 = setTimeout(() => setCurrentStepIndex(3), 700);
    const stepTimer3 = setTimeout(() => setCurrentStepIndex(4), 1050);

    try {
      // Call the real Next.js API route that connects to live FalkorDB via Python Orchestrator
      const res = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: query,
          user_id: userProfile.user_id,
          graph_off: graphOffMode,
        }),
      });

      clearTimeout(stepTimer1);
      clearTimeout(stepTimer2);
      clearTimeout(stepTimer3);

      if (res.ok) {
        const data = await res.json();
        setIsProcessing(false);
        setCurrentStepIndex(0);

        const agentMsgId = `agent-${Date.now()}`;
        const agentMessage: ChatMessage = {
          id: agentMsgId,
          sender: "agent",
          text: data.explanation || data.text || (data.verdict ? `Verdict: ${data.verdict.outcome}` : "Completed"),
          explanation: data.explanation,
          timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
          task_id: data.task_id,
          proposal: data.proposal,
          outcome: data.verdict?.outcome,
          allowed_amount_usd: data.verdict?.allowed_amount_usd,
          findings: data.verdict?.findings || [],
          gate_token: data.gate_token,
          graphOff: graphOffMode,
          abstention_active: data.abstention_active,
          isLiveFalkorDB: true,
        };

        setMessages((prev) => [...prev, agentMessage]);
        if (data.verdict) {
          setExpandedTraceId(agentMsgId);
        }
        return;
      }
    } catch (err) {
      console.warn("API route unavailable, executing direct engine...", err);
    }

    // Fallback: Execute local engine if API endpoint is unavailable
    clearTimeout(stepTimer1);
    clearTimeout(stepTimer2);
    clearTimeout(stepTimer3);

    // Parse protocol from query
    let targetProtocol = "aave-v3";
    const lower = query.toLowerCase();
    for (const node of GRAPH_NODES) {
      if (node.label === "Protocol" && (lower.includes(node.name.toLowerCase()) || lower.includes(node.id.toLowerCase()))) {
        targetProtocol = node.id;
        break;
      }
    }
    if (lower.includes("euler")) targetProtocol = "euler-v2";

    let amount = 5000;
    const m = query.match(/\$?([0-9,]+)/);
    if (m) {
      const parsed = parseFloat(m[1].replace(/,/g, ""));
      if (!isNaN(parsed) && parsed > 0) amount = parsed;
    }

    const localResult: PipelineResult = runAgentPipeline(
      { protocol_id: targetProtocol, amount_usd: amount },
      userProfile,
      graphOffMode
    );

    setIsProcessing(false);
    setCurrentStepIndex(0);

    const agentMsgId = `agent-${Date.now()}`;
    const agentMessage: ChatMessage = {
      id: agentMsgId,
      sender: "agent",
      text: localResult.guardian_report || `Verdict: ${localResult.verdict.outcome}`,
      explanation: localResult.guardian_report,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      task_id: localResult.task_id,
      proposal: localResult.proposal,
      outcome: localResult.verdict.outcome,
      allowed_amount_usd: localResult.verdict.allowed_amount_usd,
      findings: localResult.verdict.findings.map((f) => ({
        id: f.id,
        rule: f.rule,
        severity: f.severity,
        summary: f.message,
        action: f.action,
        evidence: f.evidence,
      })),
      gate_token: localResult.gate_token?.token || null,
      graphOff: graphOffMode,
      abstention_active: localResult.abstention_active,
      isLiveFalkorDB: false,
    };

    setMessages((prev) => [...prev, agentMessage]);
    setExpandedTraceId(agentMsgId);
  };

  const handleExecuteTrade = (messageId: string, msg: ChatMessage) => {
    if (!msg.gate_token || !msg.proposal) return;
    onTradeExecuted?.(
      msg.proposal.protocol_id,
      msg.allowed_amount_usd || 0,
      msg.gate_token
    );

    setMessages((prev) =>
      prev.map((m) => (m.id === messageId ? { ...m, tradeExecuted: true } : m))
    );

    const confirmMsg: ChatMessage = {
      id: `confirm-${Date.now()}`,
      sender: "agent",
      text: `🎉 **Paper Trade Executed & Committed to FalkorDB!**
- **Protocol**: ${GRAPH_NODES.find((n) => n.id === msg.proposal?.protocol_id)?.name || msg.proposal.protocol_id}
- **Authorized Amount**: $${(msg.allowed_amount_usd || 0).toLocaleString()} USD
- **Gate Token**: \`${msg.gate_token.slice(0, 20)}...\`
- **Memory Graph**: Recorded new position into \`mem_${userProfile.user_id}\`. Updated in Header and Tenant Memory view.`,
      timestamp: new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
      isLiveFalkorDB: true,
    };

    setMessages((prev) => [...prev, confirmMsg]);
  };

  return (
    <div className={isFloating ? "h-full flex flex-col min-h-0 bg-[#ffffff]" : "space-y-6"}>
      {/* Top Banner: FalkorDB Real Engine Status & Grounding Toggle */}
      {isFloating ? (
        <div className="flex items-center justify-between px-3.5 py-2 bg-[#f3f1ed] border-b border-[#d8d4d4] text-[11px] font-mono shrink-0">
          <div className="flex items-center gap-1.5">
            <span className="text-[#888888]">Tenant:</span>
            <span className="font-bold text-[#181011]">{userProfile.user_id}</span>
            <span className="text-[9px] bg-emerald-50 text-emerald-700 border border-emerald-200 px-1 py-0.2 rounded font-mono">
              :6379
            </span>
          </div>

          <div className="flex items-center gap-1">
            <button
              onClick={() => setGraphOffMode(false)}
              className={`px-2 py-0.5 rounded text-[10px] transition-colors ${
                !graphOffMode
                  ? "bg-[#181011] text-[#ffffff] font-bold"
                  : "text-[#666666] hover:text-[#181011]"
              }`}
            >
              FalkorDB
            </button>
            <button
              onClick={() => setGraphOffMode(true)}
              className={`px-2 py-0.5 rounded text-[10px] transition-colors ${
                graphOffMode
                  ? "bg-red-700 text-[#ffffff] font-bold"
                  : "text-[#666666] hover:text-red-700"
              }`}
            >
              Baseline
            </button>
          </div>
        </div>
      ) : (
        <div className="bg-[#ffffff] border border-[#d8d4d4] rounded-[4px] p-4 flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-[4px] bg-[#181011] text-[#ffffff] flex items-center justify-center font-mono text-lg font-bold">
              ⚡
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="font-mono text-[13px] font-bold text-[#181011]">
                  Bulwark Tri-Agent Investment Assistant
                </span>
                <span className="text-[10px] bg-emerald-50 text-emerald-700 border border-emerald-200 px-1.5 py-0.5 rounded font-mono">
                  LIVE FALKORDB
                </span>
              </div>
              <div className="text-[11px] font-mono text-[#666666]">
                User: <span className="font-semibold text-[#181011]">{userProfile.user_id}</span> ({(userProfile.preferences?.risk_tolerance || "balanced").toUpperCase()} Risk Tier) · GraphBLAS Sparse Engine
              </div>
            </div>
          </div>

          {/* Mode Toggle: Grounded vs Baseline */}
          <div className="flex items-center gap-2 bg-[#f3f1ed] p-1 rounded border border-[#d8d4d4] text-[11px] font-mono">
            <span className="text-[#888888] px-2">Grounding:</span>
            <button
              onClick={() => setGraphOffMode(false)}
              className={`px-3 py-1 rounded transition-colors ${
                !graphOffMode
                  ? "bg-[#181011] text-[#ffffff] font-bold"
                  : "text-[#666666] hover:text-[#181011]"
              }`}
            >
              FalkorDB Active
            </button>
            <button
              onClick={() => setGraphOffMode(true)}
              className={`px-3 py-1 rounded transition-colors ${
                graphOffMode
                  ? "bg-red-700 text-[#ffffff] font-bold"
                  : "text-[#666666] hover:text-red-700"
              }`}
            >
              Graph-Off (Ungrounded LLM)
            </button>
          </div>
        </div>
      )}

      {/* Main Chat Stream Interface */}
      <div className={isFloating ? "flex-1 flex flex-col min-h-0 overflow-hidden" : "bg-[#ffffff] border border-[#d8d4d4] rounded-[4px] flex flex-col h-[680px] shadow-xs overflow-hidden"}>
        {/* Chat Messages */}
        <div className={`flex-1 overflow-y-auto space-y-4 bg-[#faf9f8] min-h-0 ${isFloating ? "p-3.5" : "p-5"}`}>
          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`flex flex-col ${
                msg.sender === "user" ? "items-end" : "items-start"
              }`}
            >
              <div className="flex items-center gap-2 mb-1 px-1">
                <span className="text-[10px] font-mono font-bold uppercase text-[#888888]">
                  {msg.sender === "user" ? `Trader (${userProfile.user_id})` : "Bulwark Risk Agent"}
                </span>
                <span className="text-[9px] font-mono text-[#aaaaaa]">{msg.timestamp}</span>
                {msg.isLiveFalkorDB && (
                  <span className="text-[8px] bg-emerald-50 text-emerald-700 border border-emerald-200 px-1 rounded font-mono">
                    FalkorDB :6379
                  </span>
                )}
              </div>

              {/* Message Bubble */}
              <div
                className={`max-w-[88%] rounded-[4px] p-4 text-[13px] leading-relaxed font-sans ${
                  msg.sender === "user"
                    ? "bg-[#181011] text-[#ffffff] font-medium"
                    : "bg-[#ffffff] text-[#181011] border border-[#d8d4d4] shadow-xs"
                }`}
              >
                {/* Formatted Text Content */}
                <FormattedMessage content={msg.text} isUser={msg.sender === "user"} />

                {/* Abstention Warning Badge */}
                {msg.abstention_active && (
                  <div className="mt-2.5 p-2 bg-amber-50 border border-amber-200 rounded text-[11px] font-mono text-amber-800">
                    ⚠️ <strong>Epistemic Abstention Rule Active</strong>: Absence of evidence in the graph is not evidence of safety. Capital cap or gate refusal applied.
                  </div>
                )}

                {/* If message has verdict results: In-Chat Action Bar */}
                {msg.outcome && (
                  <div className="mt-4 pt-3 border-t border-[#d8d4d4] space-y-3 font-mono">
                    <div className="flex flex-wrap items-center justify-between gap-2 bg-[#f3f1ed] p-2.5 rounded border border-[#d8d4d4]">
                      <div className="flex items-center gap-2">
                        <span className="text-[10px] text-[#666666]">VERDICT:</span>
                        <span
                          className={`text-[11px] font-bold px-2 py-0.5 rounded ${
                            msg.outcome === "ALLOW"
                              ? "bg-emerald-100 text-emerald-800 border border-emerald-300"
                              : msg.outcome === "ALLOW_WITH_CAP" || msg.outcome === "WARN"
                              ? "bg-amber-100 text-amber-800 border border-amber-300"
                              : "bg-red-100 text-red-800 border border-red-300"
                          }`}
                        >
                          {msg.outcome}
                        </span>
                        <span className="text-[11px] font-bold text-[#181011]">
                          ${(msg.allowed_amount_usd || 0).toLocaleString()} USD Authorized
                        </span>
                      </div>

                      <div className="flex items-center gap-2">
                        {msg.gate_token && !msg.tradeExecuted && (
                          <button
                            onClick={() => handleExecuteTrade(msg.id, msg)}
                            className="px-3 py-1 bg-[#181011] text-[#ffffff] hover:bg-[#302023] text-[11px] rounded transition-colors font-bold shadow-xs"
                          >
                            ⚡ Confirm &amp; Execute Trade
                          </button>
                        )}
                        {msg.tradeExecuted && (
                          <span className="text-[11px] text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded font-bold">
                            ✓ COMMITTED TO MEMORY
                          </span>
                        )}
                        {msg.proposal?.protocol_id && (
                          <button
                            onClick={() =>
                              onNavigateToVisualizer?.(msg.proposal!.protocol_id)
                            }
                            className="px-2.5 py-1 bg-[#ffffff] border border-[#d8d4d4] text-[#181011] hover:bg-[#f3f1ed] text-[11px] rounded transition-colors"
                          >
                            🔍 Inspect Topology
                          </button>
                        )}
                      </div>
                    </div>

                    {/* Expandable Trace Stepper Button */}
                    <div>
                      <button
                        onClick={() =>
                          setExpandedTraceId((curr) => (curr === msg.id ? null : msg.id))
                        }
                        className="text-[11px] text-blue-600 hover:text-blue-800 font-semibold flex items-center gap-1"
                      >
                        {expandedTraceId === msg.id ? "▼ Hide FalkorDB Traversal & Findings" : `▶ View ${msg.findings?.length || 0} FalkorDB Findings & HMAC Gate Token`}
                      </button>

                      {/* Expanded Details */}
                      {expandedTraceId === msg.id && (
                        <div className="mt-2.5 p-3 bg-[#faf9f8] border border-[#d8d4d4] rounded space-y-3 text-[11px]">
                          {/* Live Task & Token Info */}
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[10px]">
                            <div className="p-2 bg-[#ffffff] border border-[#d8d4d4] rounded">
                              <span className="text-[#888888] block">FALKORDB TASK ID</span>
                              <span className="font-bold text-[#181011]">{msg.task_id || "task_live_query"}</span>
                            </div>
                            <div className="p-2 bg-[#ffffff] border border-[#d8d4d4] rounded truncate">
                              <span className="text-[#888888] block">HMAC GATE TOKEN</span>
                              <span className="font-mono text-[#181011]">
                                {msg.gate_token ? `${msg.gate_token.slice(0, 32)}...` : "None (Blocked / Refused)"}
                              </span>
                            </div>
                          </div>

                          {/* Findings List from FalkorDB */}
                          {msg.findings && msg.findings.length > 0 && (
                            <div className="space-y-1.5 pt-1">
                              <div className="text-[10px] uppercase font-bold text-[#888888]">
                                FalkorDB Rule Invariants Evaluated ({msg.findings.length})
                              </div>
                              <div className="space-y-1 max-h-40 overflow-y-auto">
                                {msg.findings.map((f, fIdx) => (
                                  <div
                                    key={fIdx}
                                    className="p-2 bg-[#ffffff] border border-[#d8d4d4] rounded text-[10px] space-y-0.5"
                                  >
                                    <div className="flex items-center justify-between">
                                      <span className="font-bold text-[#181011]">
                                        {f.rule ? `[${f.rule}]` : "[Finding]"} {f.id || ""}
                                      </span>
                                      <span
                                        className={`px-1 rounded text-[9px] font-bold uppercase ${
                                          f.severity === "high"
                                            ? "bg-red-100 text-red-700"
                                            : f.severity === "medium"
                                            ? "bg-amber-100 text-amber-700"
                                            : "bg-blue-100 text-blue-700"
                                        }`}
                                      >
                                        {f.severity || "info"}
                                      </span>
                                    </div>
                                    <div className="text-[#444444]">{f.summary}</div>
                                  </div>
                                ))}
                              </div>
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Real-Time Processing Stepper */}
          {isProcessing && (
            <div className="flex flex-col items-start space-y-2">
              <span className="text-[10px] font-mono font-bold uppercase text-[#888888] px-1">
                FalkorDB Autonomous Agent Engine
              </span>
              <div className="bg-[#ffffff] border border-[#d8d4d4] rounded-[4px] p-4 max-w-[85%] shadow-xs space-y-3 font-mono text-[11px]">
                <div className="flex items-center gap-2 text-[#181011] font-bold">
                  <span className="w-2.5 h-2.5 rounded-full bg-blue-600 animate-ping"></span>
                  <span>Executing live FalkorDB queries &amp; GraphBLAS traversal...</span>
                </div>

                <div className="space-y-2 pl-2 border-l-2 border-[#d8d4d4]">
                  <div
                    className={`flex items-center gap-2 ${
                      currentStepIndex >= 1 ? "text-emerald-700 font-bold" : "text-[#aaaaaa]"
                    }`}
                  >
                    <span>{currentStepIndex > 1 ? "✓" : "▶"}</span>
                    <span>1. Ingest Query &amp; Resolve Entity Key in `defi_risk`</span>
                  </div>
                  <div
                    className={`flex items-center gap-2 ${
                      currentStepIndex >= 2 ? "text-emerald-700 font-bold" : "text-[#aaaaaa]"
                    }`}
                  >
                    <span>{currentStepIndex > 2 ? "✓" : currentStepIndex === 2 ? "▶" : "○"}</span>
                    <span>2. Query Tenant Memory (`mem_${userProfile.user_id}`) for Capital Bounds &amp; Learned Rules</span>
                  </div>
                  <div
                    className={`flex items-center gap-2 ${
                      currentStepIndex >= 3 ? "text-emerald-700 font-bold" : "text-[#aaaaaa]"
                    }`}
                  >
                    <span>{currentStepIndex > 3 ? "✓" : currentStepIndex === 3 ? "▶" : "○"}</span>
                    <span>3. Multi-Hop Cypher Traversal (Oracles, Timelocks, Exploit Incidents)</span>
                  </div>
                  <div
                    className={`flex items-center gap-2 ${
                      currentStepIndex >= 4 ? "text-emerald-700 font-bold" : "text-[#aaaaaa]"
                    }`}
                  >
                    <span>{currentStepIndex === 4 ? "▶" : "○"}</span>
                    <span>4. Tri-Agent Blackboard Synthesis &amp; HMAC Gate Token Generation</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* User Input Bar */}
        <div className="p-3 border-t border-[#d8d4d4] bg-[#ffffff]">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              handleSendMessage();
            }}
            className="flex items-center gap-2"
          >
            <input
              type="text"
              placeholder="Type any investment query (e.g. 'Invest $50,000 into Aave V3' or 'Allocate $10,000 to Euler V2')..."
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              disabled={isProcessing}
              className="flex-1 text-[13px] font-mono px-3.5 py-2.5 border border-[#d8d4d4] rounded-[4px] bg-[#faf9f8] focus:bg-[#ffffff] focus:outline-none focus:border-[#181011] transition-colors"
            />
            <button
              type="submit"
              disabled={isProcessing || !inputText.trim()}
              className="px-5 py-2.5 bg-[#181011] hover:bg-[#302023] text-[#ffffff] text-[13px] font-mono rounded-[4px] font-bold transition-colors disabled:opacity-40"
            >
              Send ➔
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};
