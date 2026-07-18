#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 2 ]; then
  echo "usage: install_dry_run_release.sh <bundle.tgz> <expected-git-sha>" >&2
  exit 2
fi

BUNDLE="$(realpath "$1")"
EXPECTED_SHA="$2"
RELEASE_ROOT="${FREQTRADE_RELEASE_ROOT:-/home/ubuntu/freqtrade-releases}"
CURRENT_LINK="${FREQTRADE_CURRENT_LINK:-/home/ubuntu/freqtrade-current}"
LEGACY_ROOT="${FREQTRADE_LEGACY_ROOT:-/home/ubuntu/freqtrade-strategies}"
DEPLOY_LOG_ROOT="${FREQTRADE_DEPLOY_LOG_ROOT:-/home/ubuntu/freqtrade-deployments}"
RUNTIME_STATE_ROOT="${FREQTRADE_RUNTIME_STATE_ROOT:-/home/ubuntu/freqtrade-runtime}"
LOCK_FILE="$DEPLOY_LOG_ROOT/deploy.lock"

mkdir -p "$RELEASE_ROOT" "$DEPLOY_LOG_ROOT" "$RUNTIME_STATE_ROOT"
exec 9>"$LOCK_FILE"
flock -n 9 || { echo "another deployment is active" >&2; exit 3; }

STAGING="$(mktemp -d "$RELEASE_ROOT/.staging.XXXXXX")"
PREVIOUS_TARGET="$(readlink -f "$CURRENT_LINK" 2>/dev/null || true)"
CRON_BACKUP="$(mktemp)"
crontab -l > "$CRON_BACKUP" 2>/dev/null || true

rollback() {
  local code=$?
  trap - EXIT
  if [ "$code" -eq 0 ]; then
    rm -rf "$STAGING" "$CRON_BACKUP"
    return
  fi
  echo "deployment failed; rolling back operational release" >&2
  if [ -n "$PREVIOUS_TARGET" ] && [ -d "$PREVIOUS_TARGET" ]; then
    ln -sfn "$PREVIOUS_TARGET" "$CURRENT_LINK"
  fi
  crontab "$CRON_BACKUP" 2>/dev/null || true
  sudo systemctl daemon-reload || true
  sudo systemctl restart freqtrade-monitor.service || true
  rm -rf "$STAGING" "$CRON_BACKUP"
  exit "$code"
}
trap rollback EXIT

tar -xzf "$BUNDLE" -C "$STAGING"
MANIFEST="$STAGING/runtime-deployment-manifest.json"
python3 - "$STAGING" "$MANIFEST" "$EXPECTED_SHA" <<'PY'
import hashlib
import json
import pathlib
import sys

root = pathlib.Path(sys.argv[1]).resolve()
manifest_path = pathlib.Path(sys.argv[2])
expected_sha = sys.argv[3]
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
if manifest.get("schema_version") != "runtime-deployment-manifest-v1":
    raise SystemExit("invalid deployment manifest schema")
if manifest.get("git_sha") != expected_sha:
    raise SystemExit("release SHA mismatch")
if manifest.get("dry_run_only") is not True:
    raise SystemExit("refusing non-dry-run release")
for item in manifest.get("files", []):
    candidate = (root / item["path"]).resolve()
    if root not in candidate.parents:
        raise SystemExit(f"release path escaped root: {item['path']}")
    data = candidate.read_bytes()
    if hashlib.sha256(data).hexdigest() != item["sha256"]:
        raise SystemExit(f"release file hash mismatch: {item['path']}")
PY

RELEASE_DIR="$RELEASE_ROOT/$EXPECTED_SHA"
if [ ! -d "$RELEASE_DIR" ]; then
  mv "$STAGING" "$RELEASE_DIR"
  STAGING="$(mktemp -d "$RELEASE_ROOT/.staging.XXXXXX")"
fi
mkdir -p "$RELEASE_DIR/user_data"
python3 - "$RELEASE_DIR/runtime-deployment-manifest.json" "$RELEASE_DIR/user_data/runtime-deployment-manifest.json" <<'PY'
import datetime
import json
import pathlib
import sys

source = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
manifest = json.loads(source.read_text(encoding="utf-8"))
manifest["deployed_at"] = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
payload = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
source.write_text(payload, encoding="utf-8")
target.write_text(payload, encoding="utf-8")
PY

ln -sfn "$RELEASE_DIR" "$CURRENT_LINK"

sudo mkdir -p /etc/systemd/system/freqtrade-monitor.service.d
sudo tee /etc/systemd/system/freqtrade-monitor.service.d/90-managed-release.conf >/dev/null <<EOF
[Service]
WorkingDirectory=$CURRENT_LINK
Environment="DEPLOYMENT_MANIFEST_FILE=$CURRENT_LINK/user_data/runtime-deployment-manifest.json"
Environment="BOT_V1130_SHADOW_DB_FILE=$LEGACY_ROOT/user_data/tradesv3_v1130_crash_rebound_shadow.dryrun.sqlite"
ExecStart=
ExecStart=/usr/bin/node $CURRENT_LINK/dashboard/start.js
EOF

if [ -s "$CRON_BACKUP" ]; then
  cron_next="$(mktemp)"
  sed "s#$LEGACY_ROOT/scripts/notify_trades.sh#$CURRENT_LINK/scripts/notify_trades.sh#g" "$CRON_BACKUP" > "$cron_next"
  sed -i '/^TRADE_MONITOR_STATE_FILE=/d; /^TRADE_NOTIFY_DELIVERY_LOG=/d' "$cron_next"
  cron_with_env="$(mktemp)"
  printf 'TRADE_MONITOR_STATE_FILE=%s/trade_monitor_state_v2.json\n' "$RUNTIME_STATE_ROOT" > "$cron_with_env"
  printf 'TRADE_NOTIFY_DELIVERY_LOG=%s/notification_delivery.log\n' "$RUNTIME_STATE_ROOT" >> "$cron_with_env"
  cat "$cron_next" >> "$cron_with_env"
  mv "$cron_with_env" "$cron_next"
  crontab "$cron_next"
  rm -f "$cron_next"
fi

sudo systemctl daemon-reload
sudo systemctl restart freqtrade-monitor.service

healthy=0
for _ in $(seq 1 20); do
  code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 3 http://127.0.0.1:8090/ 2>/dev/null || true)"
  if [ "$code" = "200" ] || [ "$code" = "401" ]; then
    healthy=1
    break
  fi
  sleep 1
done
[ "$healthy" -eq 1 ] || { echo "dashboard smoke check failed" >&2; exit 4; }

python3 "$CURRENT_LINK/deploy/reconcile_dry_run_bots.py" \
  --release "$RELEASE_DIR" \
  --legacy "$LEGACY_ROOT"

printf '{"deployed_at":"%s","git_sha":"%s","release_dir":"%s","status":"ok"}\n' \
  "$(date -Is)" "$EXPECTED_SHA" "$RELEASE_DIR" >> "$DEPLOY_LOG_ROOT/deployments.jsonl"

trap - EXIT
rm -rf "$STAGING" "$CRON_BACKUP"
echo "deployed dry-run operational release $EXPECTED_SHA"
