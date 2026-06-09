#!/bin/bash
# Validate a private live Freqtrade config before any real-money container starts.

set -euo pipefail

CONFIG="${1:-}"

if [ -z "$CONFIG" ]; then
  echo "Usage: $0 path/to/live-config.json" >&2
  exit 2
fi

if [ ! -r "$CONFIG" ]; then
  echo "Preflight failed: config is not readable: $CONFIG" >&2
  exit 2
fi

python3 - "$CONFIG" <<'PY'
import json
import os
import sys

config_path = sys.argv[1]
with open(config_path, "r", encoding="utf-8") as handle:
    config = json.load(handle)

errors = []
warnings = []

if config.get("dry_run") is not False:
    errors.append("dry_run must be false for a live config.")

api = config.get("api_server") or {}
if api.get("listen_ip_address") in {"0.0.0.0", "::"}:
    errors.append("live api_server.listen_ip_address must not bind to a public interface.")

if not api.get("jwt_secret_key") or str(api.get("jwt_secret_key")).startswith("replace-"):
    errors.append("api_server.jwt_secret_key still looks like a placeholder.")

password = os.environ.get("FREQTRADE__API_SERVER__PASSWORD") or api.get("password")
if not password or str(password).startswith("replace-") or password == "freqtrade":
    errors.append("live API password is missing or unsafe.")

order_types = config.get("order_types") or {}
if order_types.get("stoploss_on_exchange") is not True:
    errors.append("order_types.stoploss_on_exchange must be true.")

exchange = config.get("exchange") or {}
env_key = os.environ.get("FREQTRADE__EXCHANGE__KEY")
env_secret = os.environ.get("FREQTRADE__EXCHANGE__SECRET")
if not (env_key or exchange.get("key")):
    errors.append("exchange key is missing. Prefer FREQTRADE__EXCHANGE__KEY.")
if not (env_secret or exchange.get("secret")):
    errors.append("exchange secret is missing. Prefer FREQTRADE__EXCHANGE__SECRET.")

stake = float(config.get("stake_amount") or 0)
if stake <= 0 or stake > 250:
    warnings.append("first live stake should normally be between 100 and 250 USDT.")

if int(config.get("max_open_trades") or 0) != 1:
    warnings.append("first live phase should use max_open_trades=1.")

if errors:
    print("Live preflight failed:")
    for item in errors:
        print(f"- {item}")
    if warnings:
        print("Warnings:")
        for item in warnings:
            print(f"- {item}")
    sys.exit(1)

print("Live preflight passed.")
if warnings:
    print("Warnings:")
    for item in warnings:
        print(f"- {item}")
PY
