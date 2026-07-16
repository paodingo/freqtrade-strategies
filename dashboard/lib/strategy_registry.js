"use strict";

const fs = require("fs");
const path = require("path");

const REGISTRY_SCHEMA_VERSION = "strategy-registry-v1";
const REGISTRY_RELATIVE_PATH = "dashboard/config/strategy-registry.json";
const VALID_ROLES = new Set(["current", "benchmark", "shadow", "candidate", "retired"]);
const VALID_STAGES = new Set(["research", "approved", "dry_run", "live", "retired"]);
const VALID_SOURCES = new Set(["freqtrade", "sqlite"]);

let registryCache = null;

function requireNonEmptyString(value, field) {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`strategy_registry_invalid:${field}`);
  }
}

function validateStrategyRegistry(document) {
  if (!document || typeof document !== "object" || Array.isArray(document)) {
    throw new Error("strategy_registry_invalid:document");
  }
  if (document.schema_version !== REGISTRY_SCHEMA_VERSION) {
    throw new Error("strategy_registry_invalid:schema_version");
  }
  requireNonEmptyString(document.registry_id, "registry_id");
  if (!Number.isFinite(Date.parse(document.generated_at || ""))) {
    throw new Error("strategy_registry_invalid:generated_at");
  }
  requireNonEmptyString(document.research_state_path, "research_state_path");
  if (!Array.isArray(document.strategies) || document.strategies.length === 0) {
    throw new Error("strategy_registry_invalid:strategies");
  }

  const strategyIds = new Set();
  const botKeys = new Set();
  let currentCount = 0;
  for (const strategy of document.strategies) {
    requireNonEmptyString(strategy.strategy_id, "strategy_id");
    requireNonEmptyString(strategy.display_name, `${strategy.strategy_id}.display_name`);
    if (strategyIds.has(strategy.strategy_id)) {
      throw new Error(`strategy_registry_invalid:duplicate_strategy_id:${strategy.strategy_id}`);
    }
    strategyIds.add(strategy.strategy_id);
    if (!VALID_ROLES.has(strategy.role)) {
      throw new Error(`strategy_registry_invalid:role:${strategy.strategy_id}`);
    }
    if (!VALID_STAGES.has(strategy.stage)) {
      throw new Error(`strategy_registry_invalid:stage:${strategy.strategy_id}`);
    }
    currentCount += strategy.role === "current" ? 1 : 0;

    const runtime = strategy.runtime;
    if (!runtime || !VALID_SOURCES.has(runtime.source)) {
      throw new Error(`strategy_registry_invalid:runtime_source:${strategy.strategy_id}`);
    }
    requireNonEmptyString(runtime.bot_key, `${strategy.strategy_id}.runtime.bot_key`);
    if (botKeys.has(runtime.bot_key)) {
      throw new Error(`strategy_registry_invalid:duplicate_bot_key:${runtime.bot_key}`);
    }
    botKeys.add(runtime.bot_key);
    if (runtime.source === "freqtrade") {
      requireNonEmptyString(runtime.url?.env, `${strategy.strategy_id}.runtime.url.env`);
      requireNonEmptyString(runtime.url?.default, `${strategy.strategy_id}.runtime.url.default`);
    }
    if (runtime.source === "sqlite") {
      requireNonEmptyString(runtime.sqlite?.env, `${strategy.strategy_id}.runtime.sqlite.env`);
      requireNonEmptyString(runtime.sqlite?.default_relative_path, `${strategy.strategy_id}.runtime.sqlite.default_relative_path`);
      requireNonEmptyString(strategy.strategy_class, `${strategy.strategy_id}.strategy_class`);
    }
  }
  if (currentCount !== 1) {
    throw new Error(`strategy_registry_invalid:current_role_count:${currentCount}`);
  }

  for (const field of ["base_strategy_id", "challenger_strategy_id", "chart_source_strategy_id"]) {
    const strategyId = document.comparison?.[field];
    if (!strategyIds.has(strategyId)) {
      throw new Error(`strategy_registry_invalid:comparison.${field}`);
    }
  }
  return document;
}

function resolveEnv(env, key, fallback) {
  return key && env[key] ? env[key] : fallback;
}

function resolveRuntimeStrategy(strategy, projectDir, env) {
  const runtime = strategy.runtime;
  const label = resolveEnv(env, runtime.label_env, strategy.display_name);
  if (runtime.source === "freqtrade") {
    return {
      key: runtime.bot_key,
      label,
      url: resolveEnv(env, runtime.url.env, runtime.url.default),
      registryStrategyId: strategy.strategy_id,
    };
  }
  return {
    key: runtime.bot_key,
    label,
    source: "sqlite",
    botName: runtime.bot_name || strategy.display_name,
    strategy: strategy.strategy_class,
    runmode: runtime.runmode || "dry_run",
    dryRun: runtime.dry_run !== false,
    state: runtime.state || "running",
    maxOpenTrades: runtime.max_open_trades ?? 0,
    stakeAmount: runtime.stake_amount ?? null,
    stakeCurrency: runtime.stake_currency || "USDT",
    dbFile: resolveEnv(
      env,
      runtime.sqlite.env,
      path.join(projectDir, runtime.sqlite.default_relative_path),
    ),
    registryStrategyId: strategy.strategy_id,
  };
}

function readStrategyRegistry(projectDir) {
  const registryPath = path.join(projectDir, REGISTRY_RELATIVE_PATH);
  const stats = fs.statSync(registryPath);
  if (registryCache && registryCache.path === registryPath && registryCache.mtimeMs === stats.mtimeMs) {
    return registryCache.document;
  }
  const document = validateStrategyRegistry(JSON.parse(fs.readFileSync(registryPath, "utf8")));
  registryCache = { path: registryPath, mtimeMs: stats.mtimeMs, document };
  return document;
}

function getStrategyRegistryRuntime(projectDir, env = process.env) {
  const document = readStrategyRegistry(projectDir);
  const strategiesById = new Map(document.strategies.map((strategy) => [strategy.strategy_id, strategy]));
  const bots = document.strategies.map((strategy) => resolveRuntimeStrategy(strategy, projectDir, env));
  const botKeyFor = (strategyId) => strategiesById.get(strategyId)?.runtime?.bot_key || null;
  return {
    document,
    bots,
    comparison: {
      baseKey: botKeyFor(document.comparison.base_strategy_id),
      challengerKey: botKeyFor(document.comparison.challenger_strategy_id),
      chartSourceKey: botKeyFor(document.comparison.chart_source_strategy_id),
    },
  };
}

function safeResearchState(projectDir, relativePath) {
  try {
    const resolved = path.resolve(projectDir, relativePath);
    const rootWithSeparator = `${path.resolve(projectDir)}${path.sep}`;
    if (!resolved.startsWith(rootWithSeparator)) {
      throw new Error("research_state_path_outside_project");
    }
    const state = JSON.parse(fs.readFileSync(resolved, "utf8"));
    return {
      available: true,
      generated_at: state.generated_at || null,
      snapshot_id: state.snapshot_id || null,
      formal_strategy: state.formal_strategy || null,
      state_conflict_count: Array.isArray(state.state_conflicts) ? state.state_conflicts.length : null,
    };
  } catch {
    return {
      available: false,
      generated_at: null,
      snapshot_id: null,
      formal_strategy: null,
      state_conflict_count: null,
    };
  }
}

module.exports = {
  REGISTRY_RELATIVE_PATH,
  REGISTRY_SCHEMA_VERSION,
  getStrategyRegistryRuntime,
  readStrategyRegistry,
  safeResearchState,
  validateStrategyRegistry,
};
