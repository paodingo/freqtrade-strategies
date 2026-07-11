# Freqtrade Version Selection

Recorded: 2026-07-10

## Candidates

| Candidate | Evidence | Compatibility Risk | Status |
|---|---|---|---|
| `freqtradeorg/freqtrade:stable` | `DEPLOY.md`, `scripts/run_tests.sh`, `scripts/start_bot.sh`, and `scripts/refresh_data.sh` use the Docker stable image. | Mutable tag, not reproducible as a local runtime contract. | Rejected for pinned research runtime. |
| `freqtrade==2024.5` | Existing provisional lock in `research/runtime/requirements-freqtrade.lock.txt`; strategy family uses `INTERFACE_VERSION = 3`; tests expect callbacks such as `custom_entry_price`, `custom_exit_price`, and `adjust_trade_position`. | Current dependency resolver selects a NumPy/Pandas-TA set that makes the CLI fail. | Rejected after provisioning probe. |
| `freqtrade==2025.8` | First probed fixed PyPI version after 2024.x/early-2025 dependency conflicts that installs on Python 3.12.13 and runs `python -m freqtrade --version` successfully. Still uses a fixed version, not a mutable latest tag. | Strategy callbacks must still be validated by a real backtest. | Selected provisioning candidate. |

## Strategy Interface Evidence

- `strategies/regime_aware_base.py` imports `IStrategy`, `Trade`,
  `CandleType`, and `merge_informative_pair`, and declares
  `INTERFACE_VERSION = 3`.
- `strategies/regime_aware_base.py` implements `custom_entry_price` and
  `custom_exit_price`.
- `strategies/RegimeAwareV62.py`, `RegimeAwareV63.py`, and `RegimeAwareV64.py`
  implement `adjust_trade_position`.
- Existing local Python tests fail against a stub interface that lacks these
  callbacks, which means the fixed runtime must provide the real Freqtrade
  strategy interface.

## Final Selection

Selected candidate: `freqtrade==2025.8`

Reason: `2024.5` was the prior provisional candidate, but it could not produce
a working CLI in the current resolver environment. Versions through early 2025
either failed dependency resolution or CLI execution. `2025.8` is the first
fixed version found by probe that installs on Python 3.12.13 and runs the
Freqtrade CLI, while remaining pinned and reproducible. Mutable Docker `stable`
is useful historical evidence but is not acceptable for a reproducible local
runtime.

Verification status: `provisional`

## Provisioning Note

Initial provisioning with Python `3.11.9` failed during dependency resolution:
`freqtrade==2024.5` requires `pandas-ta`, and the resolver found only
`pandas-ta` candidates requiring Python `>=3.12`. The Freqtrade version remains
pinned to `2024.5`; the minimal runtime correction is to use a 64-bit Python
`3.12.x` interpreter and retry the same lock.

Second provisioning with Python `3.12.13` installed `freqtrade==2024.5`, but
`python -m freqtrade --version` failed because the resolver selected
`numpy==2.2.6` and Freqtrade 2024.5 imports `numpy.NAN`, which is absent in
NumPy 2.x. The minimal dependency correction is to keep `freqtrade==2024.5` and
pin `numpy<2` in `requirements-freqtrade.lock.txt`.

Adding `numpy<2` made the dependency set unsatisfiable because the resolver's
available `pandas-ta` candidates require `numpy>=2.2.6`. Probes showed versions
`2024.7` through `2025.7` were not acceptable in this environment. Version
`2025.8` installed and passed `python -m freqtrade --version`, so the lock was
updated to `freqtrade==2025.8`.

This status may change to `verified` only after:

1. `.venv-freqtrade/Scripts/python.exe` imports Freqtrade successfully;
2. `python -m freqtrade --version` reports `2025.8`;
3. the environment doctor passes in strict mode;
4. two independent fixed backtests produce matching core metrics and normalized
   trade hashes.
