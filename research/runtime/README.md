# Fixed Freqtrade Runtime

This directory defines the local, isolated runtime expected by fixed Research
Campaign backtests.

The runner must invoke:

```text
.venv-freqtrade/Scripts/python.exe -m freqtrade backtesting ...
```

Codex must not install dependencies, search global `PATH`, pick another Python,
or create a fake Freqtrade module for acceptance. If `.venv-freqtrade` is absent,
`scripts/research_environment_doctor.py` reports `runtime_python_missing` and the
Campaign fails as `infra_permanent`.

Provisioning checklist:

1. Create `.venv-freqtrade` locally.
2. Install exactly `research/runtime/requirements-freqtrade.lock.txt`.
3. Confirm `.venv-freqtrade/Scripts/python.exe -m freqtrade --version` reports `2025.8`.
4. Re-run the environment doctor in strict mode before any real backtest.
