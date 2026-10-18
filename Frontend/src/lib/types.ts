export type EntityType =
  | "Protocol"
  | "Chain"
  | "Oracle"
  | "Controller"
  | "Stablecoin"
  | "Bridge"
  | "Incident"
  | "Pool"
  | "Evidence";

export type RelationshipType =
  | "USES_ORACLE"
  | "DEPENDS_ON"
  | "GOVERNED_BY"
  | "DEPLOYED_ON"
  | "HAS_POOL"
  | "AFFECTED_BY"
  | "ASSOCIATED_WITH_ASSET"
  | "RELATED_TO"
  | "ON_CHAIN";

export interface GraphNode {
  id: string;
  name: string;
  label: EntityType;
  category?: string;
  tvl_usd?: number;
  audits?: number | null;
  age_days?: number;
  change_1d?: number;
  change_7d?: number;
  price?: number;
  pegType?: string;
  pegMechanism?: string;
  pegDevPct?: number;
  controllerType?: "multisig" | "eoa" | "governance";
  threshold?: number;
  timelockHours?: number;
  kind?: string;
  sourceUrl?: string;
  summary?: string;
  date?: string;
  amountUsd?: number;
  symbol?: string;
  apy?: number;
  apyReward?: number;
  outlier?: boolean;
}

export interface GraphEdge {
  id: string;
  from: string;
  to: string;
  type: RelationshipType;
  strength?: number;
  confidence?: number;
  scope?: string;
  verified: boolean;
  risk_eligible: boolean;
  is_test?: boolean;
  source_url?: string;
  sourceUrl?: string;
  note?: string;
}

export interface DependencyPath {
  target: string;
  targetLabels: string[];
  hops: number;
  nodes: string[];
  relationships: string[];
  strength: number;
  evidence: {
    source_url?: string;
    verified?: boolean;
    strength?: number;
  }[];
}

export interface Finding {
  id: string;
  rule: "R1" | "R2" | "R3" | "R4" | "R5" | "R6" | "R7" | "R8" | "R9" | "S1";
  severity: "high" | "medium" | "low" | "info";
  message: string;
  path: string[];
  subject: string;
  action: "block" | "cap" | "warn" | "info";
  cap_usd?: number | null;
  evidence?: {
    kind?: string;
    source_url?: string;
    title?: string;
    summary?: string;
  }[];
  details?: Record<string, any>;
  memory_ref?: {
    kind: "rule" | "mistake";
    id: string;
    tag: string;
  };
}

export interface Proposal {
  protocol_id: string;
  amount_usd: number;
}

export interface Verdict {
  outcome: "ALLOW" | "ALLOW_WITH_CAP" | "WARN" | "BLOCK";
  proposal: Proposal;
  allowed_amount_usd: number;
  findings: Finding[];
  tags: string[];
  coverage: {
    modelled: boolean;
    dependency_paths: number;
    max_hops: number;
    gaps: string[];
  };
  did_you_mean?: string[];
  rules_version: string;
  disclaimer: string;
  message?: string;
}

export interface GateToken {
  token: string;
  issued_at: number;
  expires_at: number;
  proposal_hash: string;
  allowed_amount_usd: number;
  hmac_signature: string;
}

export interface TaskRecord {
  task_id: string;
  from_role: "user" | "analyst" | "guardian" | "executor" | "orchestrator";
  to_role: "analyst" | "guardian" | "executor" | "orchestrator" | "user";
  status: "proposed" | "analyzed" | "evaluated" | "gated" | "executed" | "refused";
  created_at: string;
  proposal: Proposal;
  payload_summary?: string;
  details?: Record<string, any>;
}

export interface MemoryRule {
  id: string;
  tag: string;
  action: "block" | "cap" | "warn";
  cap_pct?: number;
  note: string;
  promoted_from_mistake_id?: string;
  created_at: string;
}

export interface MistakeRecord {
  id: string;
  tag: string;
  summary: string;
  loss_usd: number;
  protocol_involved: string;
  occurred_at: string;
}

export interface UserPreferences {
  risk_tolerance: "conservative" | "moderate" | "aggressive";
  max_position_pct: number;
  avoid_categories: string[];
  avoid_chains: string[];
}

export interface PortfolioPosition {
  protocol_id: string;
  name: string;
  amount_usd: number;
  entered_at: string;
  gate_token?: string;
}

export interface UserProfile {
  user_id: string;
  display_name: string;
  description: string;
  capital_usd: number;
  preferences: UserPreferences;
  memory_rules: MemoryRule[];
  mistakes: MistakeRecord[];
  positions: PortfolioPosition[];
}

export interface ShockSimulationResult {
  shock_node: string;
  severity: number;
  max_hops: number;
  impacted_protocols: {
    protocol_id: string;
    name: string;
    hops: number;
    path: string[];
    path_strength: number;
    contagion_fraction: number;
    estimated_position_loss_usd: number;
    allocated_usd: number;
    tvl_usd?: number;
  }[];
  total_portfolio_loss_usd: number;
  portfolio_at_risk_pct: number;
  total_systemic_tvl_at_risk_usd?: number;
}

export interface SystemicRankItem {
  id: string;
  name: string;
  label: EntityType;
  direct_dependents_count: number;
  transitive_dependents_count: number;
  pagerank_score: number;
  systemic_tier: "CRITICAL" | "HIGH" | "ELEVATED" | "STANDARD";
}
