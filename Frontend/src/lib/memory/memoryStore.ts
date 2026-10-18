import { UserProfile, MemoryRule, MistakeRecord, UserPreferences, PortfolioPosition } from "../types";

export const DEFAULT_PROFILES: UserProfile[] = [
  {
    user_id: "institutional_guardian",
    display_name: "Apex Capital Institutional Desk",
    description: "Multi-sig risk officer operating strict capital preservation guidelines.",
    capital_usd: 5000000,
    preferences: {
      risk_tolerance: "conservative",
      max_position_pct: 20,
      avoid_categories: ["Algorithmic CDP", "Yield Aggregator"],
      avoid_chains: [],
    },
    memory_rules: [
      {
        id: "rule_01",
        tag: "admin_eoa",
        action: "block",
        note: "Zero allocation to protocols governed by single-signer EOA keys without timelocks.",
        promoted_from_mistake_id: "m_01",
        created_at: "2024-01-10",
      },
      {
        id: "rule_02",
        tag: "algorithmic_stablecoin",
        action: "block",
        note: "Refuse any position depending on uncollateralized or algorithmic peg mechanisms.",
        promoted_from_mistake_id: "m_02",
        created_at: "2023-11-04",
      },
      {
        id: "rule_03",
        tag: "shared_dependency",
        action: "cap",
        cap_pct: 25,
        note: "Limit portfolio exposure to any single price oracle infrastructure to 25% of capital.",
        created_at: "2024-03-12",
      },
    ],
    mistakes: [
      {
        id: "m_01",
        tag: "admin_eoa",
        summary: "Privately held deployer EOA rug-pulled liquidity on synthetic lending vault.",
        loss_usd: 240000,
        protocol_involved: "YieldForge v1",
        occurred_at: "2023-08-19",
      },
      {
        id: "m_02",
        tag: "algorithmic_stablecoin",
        summary: "Seigniorage death spiral caused 98% principal loss on algorithmic dollar pool.",
        loss_usd: 480000,
        protocol_involved: "Iron Cash",
        occurred_at: "2023-05-12",
      },
    ],
    positions: [
      {
        protocol_id: "aave-v3",
        name: "Aave v3 Core Market",
        amount_usd: 850000,
        entered_at: "2024-09-01",
        gate_token: "hmac_verified_0x827a",
      },
      {
        protocol_id: "compound-v3",
        name: "Compound v3 USDC Comet",
        amount_usd: 650000,
        entered_at: "2024-09-15",
        gate_token: "hmac_verified_0x449c",
      },
      {
        protocol_id: "makerdao",
        name: "MakerDAO / Sky USDS Vault",
        amount_usd: 500000,
        entered_at: "2024-10-02",
        gate_token: "hmac_verified_0x91df",
      },
    ],
  },
  {
    user_id: "defi_native_trader",
    display_name: "Autonomous High-Yield Treasury",
    description: "Active decentralized portfolio optimizing yield within moderate risk boundaries.",
    capital_usd: 1200000,
    preferences: {
      risk_tolerance: "moderate",
      max_position_pct: 35,
      avoid_categories: [],
      avoid_chains: [],
    },
    memory_rules: [
      {
        id: "rule_trader_01",
        tag: "young_protocol",
        action: "cap",
        cap_pct: 10,
        note: "Limit allocation to protocols listed less than 90 days to 10% of portfolio.",
        promoted_from_mistake_id: "m_trader_01",
        created_at: "2024-02-18",
      },
    ],
    mistakes: [
      {
        id: "m_trader_01",
        tag: "young_protocol",
        summary: "Fork protocol exploit wiped out newly launched lending market reserves.",
        loss_usd: 65000,
        protocol_involved: "SushiLend Fork",
        occurred_at: "2023-12-04",
      },
    ],
    positions: [
      {
        protocol_id: "lido",
        name: "Lido Liquid Staking",
        amount_usd: 300000,
        entered_at: "2024-08-20",
        gate_token: "hmac_verified_0x11ab",
      },
      {
        protocol_id: "morpho",
        name: "Morpho Blue Prime Vault",
        amount_usd: 200000,
        entered_at: "2024-09-10",
        gate_token: "hmac_verified_0x33cf",
      },
    ],
  },
  {
    user_id: "conservative_dao",
    display_name: "Community DAO Reserve Guard",
    description: "Ultra-conservative governance reserve managed strictly under formal quorum rules.",
    capital_usd: 10000000,
    preferences: {
      risk_tolerance: "conservative",
      max_position_pct: 15,
      avoid_categories: ["Derivatives", "Yield"],
      avoid_chains: ["Optimism"],
    },
    memory_rules: [
      {
        id: "rule_dao_01",
        tag: "unaudited_listed",
        action: "block",
        note: "Strictly forbid capital allocation to unreviewed smart contract bytecode.",
        created_at: "2023-09-01",
      },
    ],
    mistakes: [],
    positions: [
      {
        protocol_id: "aave-v3",
        name: "Aave v3 Core Market",
        amount_usd: 1200000,
        entered_at: "2024-07-15",
        gate_token: "hmac_verified_0x77ee",
      },
    ],
  },
];
