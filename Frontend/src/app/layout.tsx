import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import { TenantProvider } from "@/lib/context/TenantContext";
import { FloatingAgentChat } from "@/components/FloatingAgentChat";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Bulwark — Autonomous DeFi Risk Guardian on FalkorDB",
  description:
    "Engineering dossier and deterministic relational risk guardian for decentralized protocols. Multi-hop dependency intelligence, HMAC action gating, and tenant-isolated episodic memory.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col bg-[#f3f1ed] text-[#181011]">
        <TenantProvider>
          {children}
          {/* Global Floating AI Agent Chat Widget on all pages */}
          <FloatingAgentChat />
        </TenantProvider>
      </body>
    </html>
  );
}
