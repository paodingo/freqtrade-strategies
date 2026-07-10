const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const planPath = path.join(
  root,
  "reports",
  "v1131_observation",
  "v1131_longer_replay_data_acquisition_plan.json",
);
const inventoryPath = path.join(
  root,
  "reports",
  "v1131_observation",
  "v1131_longer_replay_data_source_inventory.json",
);
const outputJsonPath = path.join(
  root,
  "reports",
  "v1131_observation",
  "v1131_longer_replay_data_acquisition_execution_report.json",
);
const outputMarkdownPath = path.join(
  root,
  "reports",
  "v1131_observation",
  "v1131_longer_replay_data_acquisition_execution_report.md",
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

const plan = readJson(planPath);
const inventory = readJson(inventoryPath);
const current = plan.current_evidence_state || {};
const pairs = current.approved_pair_set?.pairs || inventory.approved_pair_set?.pairs || [];
const targets = plan.acquisition_plan?.acquisition_targets || [];

const targetResults = targets.map((target) => ({
  pair: target.pair,
  observed_15m_source_path: target.observed_15m_source_path,
  observed_15m_rows_from_prior_inventory: target.observed_15m_rows,
  execution_checked_this_task: false,
  source_file_rechecked: "not_executed",
  local_window_artifact_created: false,
  four_hour_source_discovered: false,
  four_hour_state: target.required_future_4h_source_discovery ? "unknown" : "not_applicable",
}));

const report = {
  metadata: {
    strategy: "RegimeAwareV1131LooseRangeWatchShadow",
    report_status: "execution_report_builder_without_execution",
    generated_at: new Date().toISOString(),
    sources: [
      "reports/v1131_observation/v1131_longer_replay_data_acquisition_plan.json",
      "reports/v1131_observation/v1131_longer_replay_data_source_inventory.json",
      "reports/audits/task162_v1131_longer_replay_data_acquisition_execution_authorization.md",
      "reports/audits/task168_v1131_longer_replay_data_acquisition_execution_report_guard_exception.md",
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
  execution_status: {
    acquisition_executed: false,
    reason: "This task builds the execution report artifact from committed evidence only; no server/source acquisition was performed.",
    can_use_as_longer_replay_evidence: false,
  },
  prior_evidence_summary: {
    approved_pairs: pairs,
    "15m": {
      state: current["15m"]?.state || "unknown",
      total_rows_per_pair_in_source: current["15m"]?.total_rows_per_pair_in_source || "unknown",
      committed_replay_rows_per_pair: current["15m"]?.committed_replay_rows_per_pair || "unknown",
      committed_replay_days_per_pair: current["15m"]?.committed_replay_days_per_pair || "unknown",
      supports_7d_review: current["15m"]?.supports_7d_review === true,
      supports_14d_review: current["15m"]?.supports_14d_review === true,
    },
    "4h": {
      state: current["4h"]?.state || "unknown",
      path: current["4h"]?.path || "unknown",
      rows: current["4h"]?.rows || "unknown",
    },
    alpha_taker_protection: current.alpha_taker_protection || {},
  },
  target_results: targetResults,
  field_availability_after_this_task: {
    aligned_7d_15m_window: "missing",
    aligned_14d_15m_window: "missing",
    aligned_4h_informative_window: "unknown",
    alpha_risk_timeline: "unknown",
    taker_buy_pressure_timeline: "unknown",
    taker_sell_pressure_timeline: "unknown",
    protection_or_pairlock_timeline: "unknown",
  },
  decisions: {
    can_run_longer_replay_backtest: false,
    can_deploy_shadow: false,
    can_claim_profitability: false,
    can_evaluate_replacement: false,
    next_required_task: "Task 174: V11.31 Longer Replay Data Acquisition Execution Authorization With Exact Output Paths",
  },
  blocking_gaps: [
    "No server/source acquisition was executed in this task.",
    "No aligned 7d or 14d local replay window artifact was created.",
    "4h informative source paths remain unknown.",
    "Alpha/taker/protection timelines remain unknown.",
    "Backtest remains blocked until a later task creates and reviews actual longer-window evidence.",
  ],
};

const markdown = [
  "# V11.31 Longer Replay Data Acquisition Execution Report",
  "",
  "## Summary",
  "",
  "This report artifact was generated from committed evidence only. No server access, data acquisition, data copy, backtest, strategy/config edit, or bot lifecycle command was performed.",
  "",
  "## Execution Status",
  "",
  row(["field", "value"]),
  row(["---", "---"]),
  row(["acquisition executed", String(report.execution_status.acquisition_executed)]),
  row(["can use as longer replay evidence", String(report.execution_status.can_use_as_longer_replay_evidence)]),
  row(["reason", report.execution_status.reason]),
  "",
  "## Prior Evidence Summary",
  "",
  row(["field", "value"]),
  row(["---", "---"]),
  row(["approved pairs", pairs.join(", ")]),
  row(["15m source rows per pair", String(report.prior_evidence_summary["15m"].total_rows_per_pair_in_source)]),
  row(["committed replay rows per pair", String(report.prior_evidence_summary["15m"].committed_replay_rows_per_pair)]),
  row(["committed replay days per pair", String(report.prior_evidence_summary["15m"].committed_replay_days_per_pair)]),
  row(["supports 7d review", String(report.prior_evidence_summary["15m"].supports_7d_review)]),
  row(["supports 14d review", String(report.prior_evidence_summary["15m"].supports_14d_review)]),
  row(["4h source state", report.prior_evidence_summary["4h"].state]),
  "",
  "## Target Results",
  "",
  row(["pair", "15m source path", "prior rows", "rechecked", "4h state"]),
  row(["---", "---", "---", "---", "---"]),
  ...targetResults.map((target) =>
    row([
      target.pair,
      target.observed_15m_source_path,
      String(target.observed_15m_rows_from_prior_inventory),
      String(target.execution_checked_this_task),
      target.four_hour_state,
    ]),
  ),
  "",
  "## Field Availability After This Task",
  "",
  row(["field", "state"]),
  row(["---", "---"]),
  ...Object.entries(report.field_availability_after_this_task).map(([key, value]) => row([key, value])),
  "",
  "## Blocking Gaps",
  "",
  ...report.blocking_gaps.map((item) => `- ${item}`),
  "",
  "## Decisions",
  "",
  row(["decision", "value"]),
  row(["---", "---"]),
  row(["can run longer replay backtest", String(report.decisions.can_run_longer_replay_backtest)]),
  row(["can deploy shadow", String(report.decisions.can_deploy_shadow)]),
  row(["can claim profitability", String(report.decisions.can_claim_profitability)]),
  row(["can evaluate replacement", String(report.decisions.can_evaluate_replacement)]),
  "",
  "## Recommended Next Task",
  "",
  report.decisions.next_required_task,
  "",
].join("\n");

writeJson(outputJsonPath, report);
writeText(outputMarkdownPath, markdown);
console.log(`wrote ${path.relative(root, outputJsonPath)}`);
console.log(`wrote ${path.relative(root, outputMarkdownPath)}`);

