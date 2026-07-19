export type StrategyRole = "current" | "benchmark" | "shadow" | "candidate" | "retired";
export type StrategyStage = "research" | "approved" | "dry_run" | "live" | "retired";

export interface RuntimeObservation {
  bot_key: string;
  source: "freqtrade" | "sqlite";
  observed_at: string;
  ok: boolean;
  state: string | null;
  runmode: string | null;
  dry_run: boolean | null;
  bot_name: string | null;
  latency_ms: number | null;
  open_trade_count: number | null;
  status_reason: string | null;
}

export interface PerformanceObservation {
  available: boolean;
  currency: string;
  realized_profit_abs: number | null;
  unrealized_profit_abs: number | null;
  total_profit_abs: number | null;
  total_profit_pct: number | null;
  trade_count: number | null;
  closed_trade_count: number | null;
  win_rate: number | null;
  profit_factor: number | null;
  current_drawdown_abs: number | null;
  max_drawdown_abs: number | null;
  status_reason: string | null;
}

export interface StrategyCapabilities {
  live_status: boolean;
  positions: boolean;
  performance: boolean;
  research_evidence: boolean;
}

export interface StrategyRecord {
  strategy_id: string;
  display_name: string;
  version: string | null;
  role: StrategyRole;
  stage: StrategyStage;
  strategy_class: string | null;
  description: string;
  capabilities: StrategyCapabilities;
  runtime: RuntimeObservation;
  performance: PerformanceObservation;
}

export interface FormalResearchStrategy {
  name: string;
  path: string;
  sha256: string;
  evidence?: string[];
}

export type DataReliabilityStatus = "reliable" | "degraded" | "stale" | "incomplete" | "blocked";

export interface DataReliabilityCheck {
  id: string;
  status: DataReliabilityStatus;
  severity: "info" | "warning" | "critical";
  message: string;
  blocks_decisions: boolean;
  observed_value: unknown;
}

export interface DataReliabilityReport {
  available: boolean;
  schema_version: "data-reliability-report-v1";
  checked_at: string | null;
  overall_status: DataReliabilityStatus;
  decision_allowed: boolean;
  summary: {
    check_count: number;
    reliable_count: number;
    issue_count: number;
    blocking_count: number;
  };
  checks: DataReliabilityCheck[];
  issues: DataReliabilityCheck[];
  repairs: Array<{
    action: string;
    reason: string;
    status: "succeeded" | "failed";
    started_at: string;
    completed_at: string;
    detail: string;
  }>;
  status_reason: string | null;
}

export interface StrategyRegistryResponse {
  schema_version: "strategy-registry-response-v1";
  registry: {
    schema_version: "strategy-registry-v1";
    registry_id: string;
    generated_at: string;
    authority: {
      kind: "deployment_runtime_manifest";
      description: string;
    };
  };
  comparison: {
    base_strategy_id: string;
    challenger_strategy_id: string;
    chart_source_strategy_id: string;
  };
  deployment: {
    available: boolean;
    schema_version: "runtime-deployment-manifest-v1";
    release_id: string | null;
    git_sha: string | null;
    git_short_sha: string | null;
    environment: string | null;
    dry_run_only: boolean | null;
    built_at: string | null;
    deployed_at: string | null;
    status_reason: string | null;
  };
  data_reliability: DataReliabilityReport;
  strategies: StrategyRecord[];
  research: {
    available: boolean;
    generated_at: string | null;
    snapshot_id: string | null;
    formal_strategy: FormalResearchStrategy | null;
    state_conflict_count: number | null;
  };
  freshness: {
    observed_at: string;
    refresh_hint_seconds: number;
    registry_age_seconds: number | null;
    research_age_seconds: number | null;
  };
}

export function assertStrategyRegistryResponse(value: unknown): asserts value is StrategyRegistryResponse {
  if (!value || typeof value !== "object") {
    throw new Error("strategy_registry_response_invalid:document");
  }
  const response = value as Partial<StrategyRegistryResponse>;
  if (response.schema_version !== "strategy-registry-response-v1") {
    throw new Error("strategy_registry_response_invalid:schema_version");
  }
  if (!Array.isArray(response.strategies)) {
    throw new Error("strategy_registry_response_invalid:strategies");
  }
  if (!response.data_reliability || response.data_reliability.schema_version !== "data-reliability-report-v1") {
    throw new Error("strategy_registry_response_invalid:data_reliability");
  }
  if (typeof response.data_reliability.decision_allowed !== "boolean") {
    throw new Error("strategy_registry_response_invalid:data_reliability_decision");
  }
  if (!response.data_reliability.summary || !Array.isArray(response.data_reliability.issues)) {
    throw new Error("strategy_registry_response_invalid:data_reliability_details");
  }
  const currentCount = response.strategies.filter((strategy) => strategy.role === "current").length;
  if (response.strategies.length > 0 && currentCount !== 1) {
    throw new Error(`strategy_registry_response_invalid:current_role_count:${currentCount}`);
  }
}

export async function fetchStrategyRegistry(signal?: AbortSignal): Promise<StrategyRegistryResponse> {
  const response = await fetch("/api/strategy-registry", {
    cache: "no-store",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) {
    throw new Error(`strategy_registry_request_failed:${response.status}`);
  }
  const payload: unknown = await response.json();
  assertStrategyRegistryResponse(payload);
  return payload;
}
