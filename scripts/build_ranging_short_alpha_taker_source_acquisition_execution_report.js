const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const planPath = path.join(root, "reports", "ranging_short_research", "ranging_short_alpha_taker_source_acquisition_plan.json");
const outputJsonPath = path.join(root, "reports", "ranging_short_research", "ranging_short_alpha_taker_source_acquisition_execution_report.json");
const outputMarkdownPath = path.join(root, "reports", "ranging_short_research", "ranging_short_alpha_taker_source_acquisition_execution_report.md");

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
const fields = plan.acquisition_field_plan || [];

const report = {
  metadata: {
    candidate_family: "ranging_short_volatility_fade",
    report_status: "execution_report_builder_without_execution",
    generated_at: new Date().toISOString(),
    sources: [
      "reports/ranging_short_research/ranging_short_alpha_taker_source_acquisition_plan.json",
      "reports/audits/task166_ranging_short_alpha_taker_source_acquisition_execution_authorization.md",
      "reports/audits/task172_ranging_short_alpha_taker_source_acquisition_execution_report_guard_exception.md",
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
    reason: "This task builds the execution report artifact from committed evidence only; no source acquisition was performed.",
    can_use_as_alpha_taker_evidence: false,
  },
  prior_research_evidence: plan.current_research_evidence || {},
  field_results: fields.map((field) => ({
    field: field.field,
    prior_state: field.current_state,
    execution_checked_this_task: false,
    acquired_source: false,
    resulting_state: field.current_state === "missing" ? "missing" : "unknown",
    note: "No execution was performed in this task.",
  })),
  decisions: {
    can_authorize_strategy_implementation: false,
    can_authorize_backtest: false,
    can_authorize_shadow_deployment: false,
    can_claim_profitability: false,
    next_required_task: "Task 178: Ranging Short Alpha/Taker Source Acquisition Execution Authorization With Exact Output Paths",
  },
  blocking_gaps: [
    "No source acquisition was executed in this task.",
    "Alpha-risk timeline remains missing.",
    "Taker-buy and taker-sell pressure timelines remain missing.",
    "Protection/pairlock and pairlist timeline states remain unknown.",
    "No strategy implementation, backtest, or deployment can be authorized from this artifact.",
  ],
};

const markdown = [
  "# Ranging Short Alpha/Taker Source Acquisition Execution Report",
  "",
  "## Summary",
  "",
  "This report artifact was generated from committed evidence only. No server access, source acquisition, strategy/config edit, bot lifecycle command, or backtest was performed.",
  "",
  "## Execution Status",
  "",
  row(["field", "value"]),
  row(["---", "---"]),
  row(["acquisition executed", String(report.execution_status.acquisition_executed)]),
  row(["can use as alpha/taker evidence", String(report.execution_status.can_use_as_alpha_taker_evidence)]),
  row(["reason", report.execution_status.reason]),
  "",
  "## Field Results",
  "",
  row(["field", "prior state", "checked", "resulting state"]),
  row(["---", "---", "---", "---"]),
  ...report.field_results.map((field) =>
    row([field.field, field.prior_state, String(field.execution_checked_this_task), field.resulting_state]),
  ),
  "",
  "## Blocking Gaps",
  "",
  ...report.blocking_gaps.map((item) => `- ${item}`),
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

