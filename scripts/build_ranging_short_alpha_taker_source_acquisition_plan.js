const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const sourcePath = path.join(
  root,
  "reports",
  "ranging_short_research",
  "ranging_short_alpha_taker_data_source_inventory.json",
);
const outputJsonPath = path.join(
  root,
  "reports",
  "ranging_short_research",
  "ranging_short_alpha_taker_source_acquisition_plan.json",
);
const outputMarkdownPath = path.join(
  root,
  "reports",
  "ranging_short_research",
  "ranging_short_alpha_taker_source_acquisition_plan.md",
);

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function writeJson(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, `${JSON.stringify(value, null, 2)}\n`);
}

function writeText(filePath, value) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, value);
}

function row(values) {
  return `| ${values.join(" | ")} |`;
}

const inventory = readJson(sourcePath);
const fields = inventory.field_source_inventory || {};

const acquisitionFields = [
  "alpha_risk_flags",
  "taker_buy_pressure",
  "taker_sell_pressure",
  "protection_blocked",
  "pairlist_included",
  "wallet_or_stake_blocked",
].map((key) => ({
  field: key,
  current_state: fields[key]?.current_state || "unknown",
  committed_source_status: fields[key]?.committed_source_status || "unknown",
  future_source_need: fields[key]?.future_source_need || "unknown",
  safe_next_action: fields[key]?.safe_next_action || "read-only source inventory only",
}));

const report = {
  metadata: {
    candidate_family: "ranging_short_volatility_fade",
    report_status: "source_acquisition_plan_only",
    generated_at: new Date().toISOString(),
    sources: [
      "reports/ranging_short_research/ranging_short_alpha_taker_data_source_inventory.json",
      "reports/audits/task154_ranging_short_alpha_taker_source_acquisition_authorization.md",
      "reports/audits/task160_ranging_short_alpha_taker_source_acquisition_plan_guard_exception.md",
    ],
    reads_secret: false,
    reads_env_files: false,
    server_access_performed_this_task: false,
    downloads_or_refreshes_data: false,
    modifies_strategy: false,
    modifies_bot_config: false,
    runs_backtest: false,
    starts_or_stops_bot: false,
    deploys_to_server: false,
    writes_sqlite: false,
  },
  current_research_evidence: inventory.current_research_evidence || {},
  acquisition_field_plan: acquisitionFields,
  future_execution_boundary: {
    can_acquire_now: false,
    future_authorization_required_before_server_access: true,
    allowed_future_questions: [
      "whether non-secret alpha-risk timeline evidence exists",
      "whether non-secret taker-buy/taker-sell pressure timelines exist",
      "whether non-secret protection/pairlock and pairlist timelines exist",
      "whether a recent 2026-07 window can be aligned to candidate timestamps",
    ],
    forbidden_actions: [
      "read .env or user_data/monitor.env",
      "read API keys, passwords, tokens, or server private keys",
      "modify strategies, bot configs, dashboard, deploy, or user_data",
      "start, stop, restart, or deploy bots",
      "run freqtrade trade or backtests",
      "claim profitability or deployability",
    ],
  },
  blocking_gaps: acquisitionFields
    .filter((item) => item.current_state !== "observed")
    .map((item) => `${item.field}: ${item.current_state}`),
  decisions: {
    can_authorize_strategy_implementation: false,
    can_authorize_backtest: false,
    can_authorize_shadow_deployment: false,
    can_claim_profitability: false,
  },
  recommended_next_task:
    "Task 166: Ranging Short Alpha/Taker Source Acquisition Execution Authorization",
};

const markdown = [
  "# Ranging Short Alpha/Taker Source Acquisition Plan",
  "",
  "## Summary",
  "",
  "This is a plan-only artifact. It does not access the server, acquire data, run backtests, modify strategy/config files, or make profitability/deployment claims.",
  "",
  "## Current Research Evidence",
  "",
  row(["field", "value"]),
  row(["---", "---"]),
  row(["candidate count", String(report.current_research_evidence.candidate_count || "unknown")]),
  row(["pair count", String(report.current_research_evidence.pair_count || "unknown")]),
  row(["latest pair data max", String(report.current_research_evidence.latest_pair_data_max || "unknown")]),
  row(["source method", String(report.current_research_evidence.source_method || "unknown")]),
  "",
  "## Acquisition Field Plan",
  "",
  row(["field", "current state", "source status", "future source need"]),
  row(["---", "---", "---", "---"]),
  ...acquisitionFields.map((item) =>
    row([item.field, item.current_state, item.committed_source_status, item.future_source_need]),
  ),
  "",
  "## Boundaries",
  "",
  "- Future execution requires separate authorization before any server access.",
  "- Missing fields remain `missing` or `unknown` until non-secret evidence proves otherwise.",
  "- No strategy implementation, backtest, shadow deployment, or profitability claim is authorized.",
  "",
  "## Blocking Gaps",
  "",
  ...report.blocking_gaps.map((item) => `- ${item}`),
  "",
  "## Recommended Next Task",
  "",
  report.recommended_next_task,
  "",
].join("\n");

writeJson(outputJsonPath, report);
writeText(outputMarkdownPath, markdown);
console.log(`wrote ${path.relative(root, outputJsonPath)}`);
console.log(`wrote ${path.relative(root, outputMarkdownPath)}`);

