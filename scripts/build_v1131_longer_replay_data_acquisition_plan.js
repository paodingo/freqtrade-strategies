const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const sourcePath = path.join(
  root,
  "reports",
  "v1131_observation",
  "v1131_longer_replay_data_source_inventory.json",
);
const outputJsonPath = path.join(
  root,
  "reports",
  "v1131_observation",
  "v1131_longer_replay_data_acquisition_plan.json",
);
const outputMarkdownPath = path.join(
  root,
  "reports",
  "v1131_observation",
  "v1131_longer_replay_data_acquisition_plan.md",
);

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function ensureDir(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
}

function pairToSafeName(pair) {
  return pair.replace("/", "_").replace(":", "_");
}

const inventory = readJson(sourcePath);
const pairs = inventory.approved_pair_set?.pairs || [];
const perPairSources = inventory.per_pair_sources || [];
const tf15 = inventory.data_source_inventory?.["15m"] || {};
const tf4h = inventory.data_source_inventory?.["4h"] || {};

const acquisitionTargets = perPairSources.map((item) => ({
  pair: item.pair,
  observed_15m_source_path: item["15m_path"],
  observed_15m_rows: item["15m_total_rows"],
  latest_observed_15m_window: item["15m_latest_window"],
  current_committed_replay_rows: item.committed_replay_rows_per_pair,
  current_committed_replay_days: item.committed_replay_days_per_pair,
  required_future_local_window_artifact: `reports/v1131_observation/data_windows/${pairToSafeName(
    item.pair,
  )}-15m-window.json`,
  required_future_4h_source_discovery: item["4h_source_state"] === "unknown",
}));

const report = {
  metadata: {
    strategy: "RegimeAwareV1131LooseRangeWatchShadow",
    report_status: "data_acquisition_plan_only",
    generated_at: new Date().toISOString(),
    sources: [
      "reports/v1131_observation/v1131_longer_replay_data_source_inventory.json",
      "reports/audits/task148_v1131_longer_replay_data_acquisition_authorization.md",
      "reports/audits/task156_v1131_data_acquisition_plan_guard_exception.md",
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
  current_evidence_state: {
    approved_pair_set: {
      state: inventory.approved_pair_set?.state || "unknown",
      pairs,
    },
    "15m": {
      state: tf15.state || "unknown",
      total_rows_per_pair_in_source: tf15.total_rows_per_pair_in_source || "unknown",
      committed_replay_rows_per_pair: tf15.committed_replay_rows_per_pair || "unknown",
      committed_replay_days_per_pair: tf15.committed_replay_days_per_pair || "unknown",
      supports_1d_review: tf15.supports_1d_review === true,
      supports_7d_review: tf15.supports_7d_review === true,
      supports_14d_review: tf15.supports_14d_review === true,
      caveat: tf15.caveat || "unknown",
    },
    "4h": {
      state: tf4h.state || "unknown",
      path: tf4h.path || "unknown",
      rows: tf4h.rows || "unknown",
      supports_7d_review: tf4h.supports_7d_review || "unknown",
      supports_14d_review: tf4h.supports_14d_review || "unknown",
      caveat: tf4h.caveat || "unknown",
    },
    alpha_taker_protection: inventory.alpha_taker_protection_status || {},
    replay_gate_state: inventory.replay_gate_state || {},
  },
  acquisition_plan: {
    purpose:
      "Prepare a bounded future task to acquire or derive longer V11.31 replay windows without modifying strategy/config files or running backtests.",
    can_acquire_now: false,
    server_access_required_for_actual_acquisition: true,
    future_authorization_required_before_server_access: true,
    approved_pair_count: pairs.length,
    acquisition_targets: acquisitionTargets,
    required_future_steps: [
      {
        step: "Confirm non-secret server/source paths for 15m data",
        allowed_shape: "read-only file existence, size, mtime, and bounded row-count evidence",
        forbidden_shape: "reading secrets, modifying data, refreshing downloads, or widening pair set",
      },
      {
        step: "Discover aligned 4h informative source paths",
        allowed_shape: "read-only path existence and row-count inventory",
        forbidden_shape: "claiming 4h coverage from 15m evidence alone",
      },
      {
        step: "Define 7d and 14d replay windows",
        allowed_shape: "window boundaries and expected row counts per approved pair/timeframe",
        forbidden_shape: "running backtests or declaring strategy quality",
      },
      {
        step: "Inventory alpha/taker/protection state",
        allowed_shape: "mark observed, missing, or unknown from non-secret evidence",
        forbidden_shape: "fabricating missing fields or reading bot credentials",
      },
    ],
  },
  non_goals: {
    no_data_acquisition_performed: true,
    no_backtest_performed: true,
    no_strategy_or_config_change: true,
    no_server_login: true,
    no_profitability_claim: true,
    no_shadow_deployment_claim: true,
  },
  decisions: {
    can_reconsider_backtest: false,
    can_deploy_shadow: false,
    can_claim_profitability: false,
    blocking_gaps: [
      "Actual longer replay data was not acquired in this task.",
      "4h informative source path and row-level coverage remain unknown.",
      "Committed replay artifacts still cover only the latest 240 15m candles per pair.",
      "Alpha/taker/protection evidence remains missing or unknown.",
      "Backtest remains blocked until a future replay gate review approves it.",
    ],
  },
  recommended_next_task:
    "Task 162: V11.31 Longer Replay Data Acquisition Execution Authorization",
};

function tableRow(values) {
  return `| ${values.join(" | ")} |`;
}

const markdown = [
  "# V11.31 Longer Replay Data Acquisition Plan",
  "",
  "## Summary",
  "",
  "This is a plan-only artifact. It does not acquire data, access the server, run backtests, modify strategy/config files, or make any profitability/deployment claim.",
  "",
  "## Current Evidence",
  "",
  tableRow(["field", "state"]),
  tableRow(["---", "---"]),
  tableRow(["approved pairs", pairs.join(", ")]),
  tableRow(["15m source rows per pair", String(report.current_evidence_state["15m"].total_rows_per_pair_in_source)]),
  tableRow(["committed replay rows per pair", String(report.current_evidence_state["15m"].committed_replay_rows_per_pair)]),
  tableRow(["committed replay days per pair", String(report.current_evidence_state["15m"].committed_replay_days_per_pair)]),
  tableRow(["15m supports 7d review", String(report.current_evidence_state["15m"].supports_7d_review)]),
  tableRow(["15m supports 14d review", String(report.current_evidence_state["15m"].supports_14d_review)]),
  tableRow(["4h source state", String(report.current_evidence_state["4h"].state)]),
  tableRow(["alpha/taker/protection", "missing or unknown"]),
  "",
  "## Acquisition Targets",
  "",
  tableRow(["pair", "observed 15m source", "rows", "committed rows", "4h discovery needed"]),
  tableRow(["---", "---", "---", "---", "---"]),
  ...acquisitionTargets.map((target) =>
    tableRow([
      target.pair,
      target.observed_15m_source_path,
      String(target.observed_15m_rows),
      String(target.current_committed_replay_rows),
      String(target.required_future_4h_source_discovery),
    ]),
  ),
  "",
  "## Future Execution Boundary",
  "",
  "- Future data acquisition requires separate authorization before any server access.",
  "- Future checks must remain read-only and non-secret.",
  "- The pair set must remain exact unless a later review explicitly changes it.",
  "- No backtest may run until a future replay gate review approves it.",
  "",
  "## Blocking Gaps",
  "",
  ...report.decisions.blocking_gaps.map((item) => `- ${item}`),
  "",
  "## Decisions",
  "",
  tableRow(["decision", "value"]),
  tableRow(["---", "---"]),
  tableRow(["can acquire now", String(report.acquisition_plan.can_acquire_now)]),
  tableRow(["can reconsider backtest", String(report.decisions.can_reconsider_backtest)]),
  tableRow(["can deploy shadow", String(report.decisions.can_deploy_shadow)]),
  tableRow(["can claim profitability", String(report.decisions.can_claim_profitability)]),
  "",
  "## Recommended Next Task",
  "",
  report.recommended_next_task,
  "",
].join("\n");

ensureDir(outputJsonPath);
fs.writeFileSync(outputJsonPath, `${JSON.stringify(report, null, 2)}\n`);
fs.writeFileSync(outputMarkdownPath, markdown);
console.log(`wrote ${path.relative(root, outputJsonPath)}`);
console.log(`wrote ${path.relative(root, outputMarkdownPath)}`);

