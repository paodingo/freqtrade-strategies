const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const sourcePath = path.join(root, "reports", "v1130_observation", "v1130_live_telemetry_window_report.json");
const outputJsonPath = path.join(
  root,
  "reports",
  "v1130_observation",
  "v1130_live_telemetry_server_collection_plan.json",
);
const outputMarkdownPath = path.join(
  root,
  "reports",
  "v1130_observation",
  "v1130_live_telemetry_server_collection_plan.md",
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

const source = readJson(sourcePath);
const runtime = source.committed_runtime_evidence || {};
const server = runtime.server_context || {};

const collectionPlan = [
  {
    evidence_type: "bounded_logs",
    state: "planned_not_executed",
    command_draft: "docker logs --tail 800 freqtrade-v1130-crash-rebound-shadow",
    purpose: "Collect bounded recent warnings/errors/analysis-cycle evidence without changing bot state.",
    forbidden: "No restart/stop/start, no full docker inspect, no secret/env reads.",
  },
  {
    evidence_type: "point_in_time_container_state",
    state: "planned_not_executed",
    command_draft: "docker ps --format '{{.Names}}\\t{{.Status}}\\t{{.Ports}}'",
    purpose: "Confirm whether the V11.30 container is running at collection time.",
    forbidden: "No container lifecycle commands.",
  },
  {
    evidence_type: "point_in_time_resource_snapshot",
    state: "planned_not_executed",
    command_draft: "docker stats --no-stream freqtrade-v1130-crash-rebound-shadow",
    purpose: "Capture CPU/memory snapshot while preserving the caveat that spikes may be intermittent.",
    forbidden: "No tuning, restart, or config modification.",
  },
  {
    evidence_type: "read_only_sqlite_counts",
    state: "planned_not_executed",
    command_draft: "sqlite3 -readonly <approved-v1130-snapshot-or-db> '<bounded count/timestamp queries>'",
    purpose: "Join runtime window with observed trades/orders only after exact path authorization.",
    forbidden: "No SQLite writes and no live DB modification.",
  },
];

const report = {
  metadata: {
    strategy: "RegimeAwareV1130CrashReboundShadow",
    report_status: "server_collection_plan_only",
    generated_at: new Date().toISOString(),
    sources: [
      "reports/v1130_observation/v1130_live_telemetry_window_report.json",
      "reports/audits/task155_v1130_live_telemetry_server_collection_authorization.md",
      "reports/audits/task161_v1130_live_telemetry_server_collection_plan_guard_exception.md",
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
  committed_runtime_evidence: {
    server_context: server,
    analysis_overrun: runtime.analysis_overrun || { state: "unknown" },
    exchange_timeout: runtime.exchange_timeout || { state: "unknown" },
    running_after_warning: runtime.running_after_warning || { state: "unknown" },
    point_in_time_resource_saturation:
      runtime.point_in_time_resource_saturation || { state: "unknown" },
  },
  telemetry_window_status: source.telemetry_window_status || {},
  future_collection_plan: collectionPlan,
  stop_conditions: [
    "worktree is dirty before execution",
    "readiness checks fail",
    "server command would read secrets or full docker inspect output",
    "command would start, stop, restart, or deploy a bot",
    "command would write SQLite, strategy, config, dashboard, or deploy files",
  ],
  decisions: {
    can_claim_runtime_stability: false,
    can_claim_profitability: false,
    can_evaluate_replacement: false,
    can_execute_collection_now: false,
  },
  recommended_next_task: "Task 167: V11.30 Live Telemetry Server Collection Execution Authorization",
};

const markdown = [
  "# V11.30 Live Telemetry Server Collection Plan",
  "",
  "## Summary",
  "",
  "This is a plan-only artifact. It does not connect to the server, read fresh logs, modify files, restart bots, or run backtests.",
  "",
  "## Committed Runtime Evidence",
  "",
  row(["field", "value"]),
  row(["---", "---"]),
  row(["host", String(server.host || "unknown")]),
  row(["hostname", String(server.hostname || "unknown")]),
  row(["last checked", String(server.server_time_checked || "unknown")]),
  row(["v1130 container", String(server.v1130_container || "unknown")]),
  row(["v1130 state", String(server.v1130_state || "unknown")]),
  row(["analysis overrun", String(runtime.analysis_overrun?.state || "unknown")]),
  row(["exchange timeout", String(runtime.exchange_timeout?.state || "unknown")]),
  "",
  "## Future Collection Plan",
  "",
  row(["evidence type", "state", "command draft"]),
  row(["---", "---", "---"]),
  ...collectionPlan.map((item) => row([item.evidence_type, item.state, item.command_draft.replace(/\|/g, "\\|")])),
  "",
  "## Stop Conditions",
  "",
  ...report.stop_conditions.map((item) => `- ${item}`),
  "",
  "## Decisions",
  "",
  row(["decision", "value"]),
  row(["---", "---"]),
  ...Object.entries(report.decisions).map(([key, value]) => row([key, String(value)])),
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

