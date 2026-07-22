# Paper Lane Recovery

## Objective

The repository is temporarily operating in a trading-loop recovery mode. Progress is measured by runtime health, executable benchmark evidence, closed dry-run trades, and explicit retain/retire decisions rather than by task or report volume.

## Active lane

- The only active runtime candidate is `RegimeAwareV1130CrashReboundShadow`.
- `RegimeAwareV1129ResidualDragMicroSizer` is retired from active execution. Its SQLite database remains read-only historical evidence.
- All runtime strategy/configuration inputs must come from an immutable dry-run release. Mutable server worktree strategy/config files are not runtime authority.
- Live trading remains forbidden.

## Temporary freeze

Until the paper lane completes its first 30-day and 50-closed-trade review, do not start:

- new descriptive pair or regime research;
- a new strategy family or parameter search;
- dashboard product expansion;
- new research governance, schema, or approval infrastructure;
- a second active Candidate.

Safety fixes, runtime reliability, executable baselines, and paper-lane measurement remain in scope.

## Runtime acceptance

The initial lane must demonstrate:

- one immutable release identity with no strategy/config drift;
- one running V11.30 container with zero restarts;
- current candles and ticker data;
- no market-reload timeout, fatal runtime event, or strategy-analysis overrun in the trailing bounded log window;
- at least 24 hours of reliability samples before Task 0193 can close.

## Next gates

1. Compare V11.30 with one simple trend baseline and one simple mean-reversion baseline using identical data, costs, and risk settings.
2. Continue only the best eligible Candidate and the best simple baseline in isolated dry-run lanes.
3. Require at least 30 calendar days and 50 closed trades before a retain/promote decision.
4. Any real-money operation requires a new explicit human approval.
