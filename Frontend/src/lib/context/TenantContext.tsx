"use client";

import React, { createContext, useContext, useState } from "react";
import { DEFAULT_PROFILES } from "@/lib/memory/memoryStore";
import { UserProfile, PortfolioPosition } from "@/lib/types";
import { GRAPH_NODES } from "@/lib/data/graphData";

interface TenantContextType {
  profiles: UserProfile[];
  currentProfile: UserProfile;
  selectProfileById: (userId: string) => void;
  updateProfile: (profile: UserProfile) => void;
  executeTrade: (protocolId: string, amountUsd: number, gateToken: string) => void;
  totalPortfolioUsd: number;
}

const TenantContext = createContext<TenantContextType | undefined>(undefined);

export const TenantProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [profiles, setProfiles] = useState<UserProfile[]>(DEFAULT_PROFILES);
  const [currentProfile, setCurrentProfile] = useState<UserProfile>(DEFAULT_PROFILES[0]);

  const selectProfileById = (userId: string) => {
    const found = profiles.find((p) => p.user_id === userId);
    if (found) setCurrentProfile(found);
  };

  const updateProfile = (updated: UserProfile) => {
    setCurrentProfile(updated);
    setProfiles((prev) =>
      prev.map((p) => (p.user_id === updated.user_id ? updated : p))
    );
  };

  const executeTrade = (
    protocolId: string,
    amountUsd: number,
    gateToken: string
  ) => {
    const protoNode = GRAPH_NODES.find((n) => n.id === protocolId);
    const newPosition: PortfolioPosition = {
      protocol_id: protocolId,
      name: protoNode?.name || protocolId,
      amount_usd: amountUsd,
      entered_at: new Date().toISOString().split("T")[0],
      gate_token: gateToken,
    };

    const updatedProfile: UserProfile = {
      ...currentProfile,
      positions: [newPosition, ...currentProfile.positions],
    };

    updateProfile(updatedProfile);
  };

  const totalPortfolioUsd = currentProfile.positions.reduce(
    (sum, p) => sum + p.amount_usd,
    0
  );

  return (
    <TenantContext.Provider
      value={{
        profiles,
        currentProfile,
        selectProfileById,
        updateProfile,
        executeTrade,
        totalPortfolioUsd,
      }}
    >
      {children}
    </TenantContext.Provider>
  );
};

export const useTenant = (): TenantContextType => {
  const context = useContext(TenantContext);
  if (!context) {
    throw new Error("useTenant must be used within a TenantProvider");
  }
  return context;
};
