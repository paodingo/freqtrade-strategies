const { execFileSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const planPath = path.join(root, "reports", "v1131_observation", "v1131_longer_replay_data_acquisition_plan.json");
const outputJsonPath = path.join(root, "reports", "v1131_observation", "v1131_longer_replay_data_acquisition_actual_execution_report.json");
const outputMarkdownPath = path.join(root, "reports", "v1131_observation", "v1131_longer_replay_data_acquisition_actual_execution_report.md");

const sshHost = process.env.V1131_SSH_HOST || "43.134.72.69";
const sshUser = process.env.V1131_SSH_USER || "ubuntu";
const sshKey = process.env.V1131_SSH_KEY || "D:\\key\\openclaw\\clf.pem";

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

function pairToStem(pair) {
  return pair.replace("/", "_").replace(":USDT", "_USDT");
}

function runSsh(remoteCommand) {
  return execFileSync(
    "ssh",
    [
      "-i",
      sshKey,
      "-o",
      "BatchMode=yes",
      "-o",
      "ConnectTimeout=10",
      "-o",
      "StrictHostKeyChecking=accept-new",
      `${sshUser}@${sshHost}`,
      remoteCommand,
    ],
    { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"] },
  );
}

function buildRemotePython(paths) {
  const payload = JSON.stringify(paths);
  return `python3 - <<'PY'\nimport json, os, datetime\npaths = ${payload}\nresult = {\"checked_at\": datetime.datetime.now(datetime.timezone.utc).isoformat(), \"files\": []}\ntry:\n    import pyarrow.feather as feather\nexcept Exception as exc:\n    feather = None\n    result[\"pyarrow_error\"] = str(exc)\nfor item in paths:\n    p = item[\"path\"]\n    rec = dict(item)\n    rec[\"exists\"] = os.path.exists(p)\n    if rec[\"exists\"]:\n        st = os.stat(p)\n        rec[\"size_bytes\"] = st.st_size\n        rec[\"mtime_utc\"] = datetime.datetime.fromtimestamp(st.st_mtime, datetime.timezone.utc).isoformat()\n        if feather is not None:\n            try:\n                table = feather.read_table(p, columns=[\"date\"])\n                rec[\"row_count\"] = table.num_rows\n                if table.num_rows:\n                    dates = table.column(\"date\").to_pylist()\n                    rec[\"first_date\"] = str(dates[0])\n                    rec[\"last_date\"] = str(dates[-1])\n            except Exception as exc:\n                rec[\"feather_error\"] = str(exc)\n    result[\"files\"].append(rec)\nprint(json.dumps(result, ensure_ascii=False, sort_keys=True))\nPY`;
}

const plan = readJson(planPath);
const pairs = plan.current_evidence_state?.approved_pair_set?.pairs || [];
const remotePaths = [];
for (const pair of pairs) {
  const stem = pairToStem(pair);
  remotePaths.push({
    pair,
    timeframe: "15m",
    path: `/freqtrade/project/user_data/data/futures/${stem}-15m-futures.feather`,
  });
  remotePaths.push({
    pair,
    timeframe: "4h",
    path: `/freqtrade/project/user_data/data/futures/${stem}-4h-futures.feather`,
  });
}

let sshEvidence;
let sshError = null;
try {
  const serverContext = runSsh("hostname; date -Is").trim().split(/\r?\n/);
  const hostRaw = runSsh(buildRemotePython(remotePaths));
  const hostEvidence = JSON.parse(hostRaw);
  const dockerRows = runSsh("docker ps --format '{{.Names}}\\t{{.Status}}'")
    .trim()
    .split(/\r?\n/)
    .filter(Boolean);
  const containers = dockerRows
    .map((line) => {
      const [name, ...statusParts] = line.split(/\t/);
      return { name, status: statusParts.join("\t") };
    })
    .filter((item) => /^freqtrade-v(1129|1130|1131)/.test(item.name));
  const containerEvidence = [];
  for (const container of containers) {
    try {
      const containerRaw = runSsh(`docker exec -i ${container.name} ${buildRemotePython(remotePaths)}`);
      const evidence = JSON.parse(containerRaw);
      evidence.container = container;
      containerEvidence.push(evidence);
    } catch (error) {
      containerEvidence.push({
        container,
        files: [],
        error: String(error.stderr || error.message || error),
      });
    }
  }
  const bestContainer = containerEvidence
    .slice()
    .sort((a, b) => {
      const aExists = (a.files || []).filter((file) => file.exists).length;
      const bExists = (b.files || []).filter((file) => file.exists).length;
      return bExists - aExists;
    })[0];
  const bestContainerHasFiles = bestContainer && (bestContainer.files || []).some((file) => file.exists);
  sshEvidence = {
    checked_at: new Date().toISOString(),
    host_files: hostEvidence.files || [],
    containers: containerEvidence,
    selected_source: bestContainerHasFiles ? `container:${bestContainer.container.name}` : "host",
    files: bestContainerHasFiles ? bestContainer.files : (hostEvidence.files || []),
  };
  sshEvidence.server = {
    host: sshHost,
    user: sshUser,
    hostname: serverContext[0] || "unknown",
    server_date: serverContext[1] || "unknown",
    docker_ps_checked: true,
    containers,
  };
} catch (error) {
  sshError = String(error.stderr || error.message || error);
  sshEvidence = { files: [], server: { host: sshHost, user: sshUser } };
}

function summarizeWindow(files, timeframe) {
  const rows = files.filter((file) => file.timeframe === timeframe);
  const existing = rows.filter((file) => file.exists);
  return {
    checked_pairs: rows.length,
    existing_files: existing.length,
    all_exist: rows.length > 0 && existing.length === rows.length,
    min_row_count: existing.length ? Math.min(...existing.map((file) => file.row_count || 0)) : "missing",
    max_row_count: existing.length ? Math.max(...existing.map((file) => file.row_count || 0)) : "missing",
    earliest_first_date: existing.map((file) => file.first_date).filter(Boolean).sort()[0] || "unknown",
    latest_last_date: existing.map((file) => file.last_date).filter(Boolean).sort().slice(-1)[0] || "unknown",
  };
}

const files = sshEvidence.files || [];
const tf15 = summarizeWindow(files, "15m");
const tf4h = summarizeWindow(files, "4h");
const canDerive7d = tf15.all_exist && tf4h.all_exist && Number(tf15.min_row_count) >= 672 && Number(tf4h.min_row_count) >= 42;
const canDerive14d = tf15.all_exist && tf4h.all_exist && Number(tf15.min_row_count) >= 1344 && Number(tf4h.min_row_count) >= 84;

const report = {
  metadata: {
    strategy: "RegimeAwareV1131LooseRangeWatchShadow",
    report_status: sshError ? "actual_acquisition_failed" : "actual_read_only_source_metadata_collected",
    generated_at: new Date().toISOString(),
    sources: [
      "reports/v1131_observation/v1131_longer_replay_data_acquisition_plan.json",
      "reports/audits/task174_v1131_longer_replay_data_acquisition_execution_authorization_with_exact_output_paths.md",
      "reports/audits/task180_v1131_actual_data_acquisition_execution_report_guard_exception.md",
    ],
    reads_secret: false,
    reads_env_files: false,
    server_access_performed_this_task: !sshError,
    downloads_or_refreshes_data: false,
    copies_source_data: false,
    modifies_strategy: false,
    modifies_bot_config: false,
    runs_backtest: false,
    starts_or_stops_bot: false,
    deploys_to_server: false,
    writes_sqlite: false,
  },
  server_context: sshEvidence.server,
  selected_source: sshEvidence.selected_source || "unknown",
  host_file_evidence: sshEvidence.host_files || [],
  container_sources_checked: sshEvidence.containers || [],
  ssh_error: sshError,
  approved_pairs: pairs,
  file_evidence: files,
  window_summary: {
    "15m": tf15,
    "4h": tf4h,
    can_derive_7d_window_from_metadata: canDerive7d,
    can_derive_14d_window_from_metadata: canDerive14d,
  },
  alpha_taker_protection_status: {
    alpha_risk_timeline: "unknown",
    taker_buy_pressure_timeline: "unknown",
    taker_sell_pressure_timeline: "unknown",
    protection_or_pairlock_timeline: "unknown",
    reason: "This task checked only non-secret OHLCV source metadata.",
  },
  decisions: {
    can_run_longer_replay_backtest: false,
    can_authorize_replay_gate_review: !sshError && canDerive7d && canDerive14d,
    can_deploy_shadow: false,
    can_claim_profitability: false,
    next_required_task: !sshError && canDerive7d && canDerive14d
      ? "Task 186: V11.31 Longer Replay Backtest Gate Review"
      : "Task 186: V11.31 Data Acquisition Gap Closure",
  },
  blocking_gaps: [
    ...(!canDerive7d ? ["7d aligned 15m+4h window is not proven from current metadata."] : []),
    ...(!canDerive14d ? ["14d aligned 15m+4h window is not proven from current metadata."] : []),
    "Alpha/taker/protection timelines remain unknown.",
    "No backtest was run in this task.",
  ],
};

const markdown = [
  "# V11.31 Actual Data Acquisition Execution Report",
  "",
  "## Summary",
  "",
  sshError
    ? `Read-only SSH metadata collection failed: ${sshError}`
    : "Read-only SSH metadata collection completed. No data was copied, refreshed, downloaded, or written.",
  "",
  "## Server Context",
  "",
  row(["field", "value"]),
  row(["---", "---"]),
  row(["host", String(report.server_context.host || "unknown")]),
  row(["user", String(report.server_context.user || "unknown")]),
  row(["hostname", String(report.server_context.hostname || "unknown")]),
  row(["server date", String(report.server_context.server_date || "unknown")]),
  row(["selected source", String(report.selected_source || "unknown")]),
  "",
  "## Window Summary",
  "",
  row(["timeframe", "existing files", "min rows", "earliest", "latest"]),
  row(["---", "---", "---", "---", "---"]),
  row(["15m", `${tf15.existing_files}/${tf15.checked_pairs}`, String(tf15.min_row_count), String(tf15.earliest_first_date), String(tf15.latest_last_date)]),
  row(["4h", `${tf4h.existing_files}/${tf4h.checked_pairs}`, String(tf4h.min_row_count), String(tf4h.earliest_first_date), String(tf4h.latest_last_date)]),
  "",
  "## File Evidence",
  "",
  row(["pair", "timeframe", "exists", "rows", "first", "last"]),
  row(["---", "---", "---", "---", "---", "---"]),
  ...files.map((file) => row([
    file.pair,
    file.timeframe,
    String(file.exists),
    String(file.row_count || "unknown"),
    String(file.first_date || "unknown"),
    String(file.last_date || "unknown"),
  ])),
  "",
  "## Decisions",
  "",
  row(["decision", "value"]),
  row(["---", "---"]),
  row(["can authorize replay gate review", String(report.decisions.can_authorize_replay_gate_review)]),
  row(["can run longer replay backtest", String(report.decisions.can_run_longer_replay_backtest)]),
  row(["can deploy shadow", String(report.decisions.can_deploy_shadow)]),
  row(["can claim profitability", String(report.decisions.can_claim_profitability)]),
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
