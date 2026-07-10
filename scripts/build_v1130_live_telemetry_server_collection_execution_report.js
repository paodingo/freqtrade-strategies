const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const planPath = path.join(root, "reports", "v1130_observation", "v1130_live_telemetry_server_collection_plan.json");
const outputJsonPath = path.join(root, "reports", "v1130_observation", "v1130_live_telemetry_server_collection_execution_report.json");
const outputMarkdownPath = path.join(root, "reports", "v1130_observation", "v1130_live_telemetry_server_collection_execution_report.md");

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
const collectionPlan = plan.future_collection_plan || [];

const report = {
  metadata: {
    strategy: "RegimeAwareV1130CrashReboundShadow",
    report_status: "execution_report_builder_without_server_collection",
    generated_at: new Date().toISOString(),
    sources: [
      "reports/v1130_observation/v1130_live_telemetry_server_collection_plan.json",
      "reports/audits/task167_v1130_live_telemetry_server_collection_execution_authorization.md",
      "reports/audits/task173_v1130_live_telemetry_server_collection_execution_report_guard_exception.md",
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
    server_collection_executed: false,
    reason: "This task builds the execution report artifact from committed evidence only; no live telemetry collection was performed.",
    can_use_as_fresh_runtime_evidence: false,
  },
  prior_runtime_evidence: plan.committed_runtime_evidence || {},
  collection_results: collectionPlan.map((item) => ({
    evidence_type: item.evidence_type,
    planned_command: item.command_draft,
    executed_this_task: false,
    resulting_state: "not_collected",
    note: "No server command was executed in this task.",
  })),
  decisions: {
    can_claim_runtime_stability: false,
    can_claim_profitability: false,
    can_evaluate_replacement: false,
    next_required_task: "Task 179: V11.30 Live Telemetry Server Collection Execution Authorization With Exact Output Paths",
  },
  blocking_gaps: [
    "No fresh server telemetry was collected in this task.",
    "Fresh Docker logs remain not collected.",
    "Fresh docker stats remain not collected.",
    "Fresh SQLite timing join remains not collected.",
    "Runtime stability and replacement evaluation remain blocked.",
  ],
};

const markdown = [
  "# V11.30 Live Telemetry Server Collection Execution Report",
  "",
  "## Summary",
  "",
  "This report artifact was generated from committed evidence only. No server login, Docker command, SQLite query, strategy/config edit, bot lifecycle command, or backtest was performed.",
  "",
  "## Execution Status",
  "",
  row(["field", "value"]),
  row(["---", "---"]),
  row(["server collection executed", String(report.execution_status.server_collection_executed)]),
  row(["can use as fresh runtime evidence", String(report.execution_status.can_use_as_fresh_runtime_evidence)]),
  row(["reason", report.execution_status.reason]),
  "",
  "## Collection Results",
  "",
  row(["evidence type", "executed", "state"]),
  row(["---", "---", "---"]),
  ...report.collection_results.map((item) =>
    row([item.evidence_type, String(item.executed_this_task), item.resulting_state]),
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

