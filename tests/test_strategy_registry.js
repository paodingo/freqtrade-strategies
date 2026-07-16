"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const test = require("node:test");

const {
  getStrategyRegistryRuntime,
  safeResearchState,
  validateStrategyRegistry,
} = require("../dashboard/lib/strategy_registry");

const PROJECT_DIR = path.resolve(__dirname, "..");
const REGISTRY_PATH = path.join(PROJECT_DIR, "dashboard/config/strategy-registry.json");

function sourceRegistry() {
  return JSON.parse(fs.readFileSync(REGISTRY_PATH, "utf8"));
}

test("strategy registry validates one current role and stable comparison identities", () => {
  const registry = validateStrategyRegistry(sourceRegistry());
  assert.equal(registry.schema_version, "strategy-registry-v1");
  assert.equal(registry.strategies.filter((strategy) => strategy.role === "current").length, 1);
  const ids = new Set(registry.strategies.map((strategy) => strategy.strategy_id));
  assert.ok(ids.has(registry.comparison.base_strategy_id));
  assert.ok(ids.has(registry.comparison.challenger_strategy_id));
  assert.ok(ids.has(registry.comparison.chart_source_strategy_id));
});

test("strategy registry rejects ambiguous current strategy roles", () => {
  const registry = sourceRegistry();
  registry.strategies[1].role = "current";
  assert.throws(
    () => validateStrategyRegistry(registry),
    /strategy_registry_invalid:current_role_count:2/,
  );
});

test("runtime bot wiring is resolved from registry data and environment overrides", () => {
  const runtime = getStrategyRegistryRuntime(PROJECT_DIR, {
    BOT_V1129_LABEL: "Current from env",
    BOT_V1129_URL: "http://127.0.0.1:9999",
  });
  const current = runtime.bots.find((bot) => bot.registryStrategyId === "runtime-v1129-current");
  const shadow = runtime.bots.find((bot) => bot.registryStrategyId === "runtime-v1130-crash-rebound-shadow");
  assert.equal(current.label, "Current from env");
  assert.equal(current.url, "http://127.0.0.1:9999");
  assert.equal(shadow.strategy, "RegimeAwareV1130CrashReboundShadow");
  assert.equal(runtime.comparison.baseKey, current.key);
  assert.equal(runtime.comparison.challengerKey, shadow.key);
});

test("research identity is read separately from runtime display roles", () => {
  const registry = sourceRegistry();
  const fixtureRoot = fs.mkdtempSync(path.join(os.tmpdir(), "strategy-registry-"));
  const fixturePath = path.join(fixtureRoot, "research-state.json");
  fs.writeFileSync(
    fixturePath,
    JSON.stringify({
      generated_at: "2026-07-16T00:00:00Z",
      formal_strategy: { name: "ResearchOnlyStrategy" },
    }),
  );

  try {
    const research = safeResearchState(fixtureRoot, "research-state.json");
    assert.equal(research.available, true);
    assert.equal(research.formal_strategy?.name, "ResearchOnlyStrategy");
    assert.notEqual(research.formal_strategy?.name, registry.strategies[0].display_name);

    const missing = safeResearchState(fixtureRoot, "missing.json");
    assert.equal(missing.available, false);
  } finally {
    fs.rmSync(fixtureRoot, { recursive: true, force: true });
  }
});

test("dashboard runtime code no longer declares version-specific bot lanes", () => {
  const config = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/lib/config.js"), "utf8");
  const server = fs.readFileSync(path.join(PROJECT_DIR, "dashboard/server.js"), "utf8");
  assert.doesNotMatch(config, /BOT_V\d+/);
  assert.doesNotMatch(config, /const\s+BOTS\s*=\s*\[/);
  assert.doesNotMatch(server, /BOTS\[[01]\]/);
  assert.match(config, /getStrategyRegistryRuntime/);
  assert.match(server, /\/api\/strategy-registry/);
});
