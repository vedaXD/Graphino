"use client";

import React from "react";
import { Header } from "@/components/Header";
import { HeroSection } from "@/components/HeroSection";
import { Footer } from "@/components/Footer";
import { useTenant } from "@/lib/context/TenantContext";

export default function Home() {
  const { profiles, currentProfile, selectProfileById } = useTenant();

  return (
    <div className="min-h-screen flex flex-col bg-[#f3f1ed] text-[#181011]">
      {/* Minimal Top Header with Direct Dashboard Link */}
      <Header
        profiles={profiles}
        currentProfile={currentProfile}
        onSelectProfile={(p) => selectProfileById(p.user_id)}
      />

      {/* Clean Minimal Landing Page Hero */}
      <main className="flex-1 flex flex-col justify-center">
        <HeroSection />
      </main>

      {/* Minimal Footer */}
      <Footer />
    </div>
  );
}
