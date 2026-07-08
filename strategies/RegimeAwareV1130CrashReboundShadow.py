"""V11.30 crash-rebound long-only dry-run shadow strategy."""

from datetime import timedelta
import json
import os
from pathlib import Path

from pandas import DataFrame

from RegimeAwareV66AlphaRisk import RegimeAwareV66AlphaRisk


class RegimeAwareV1130CrashReboundShadow(RegimeAwareV66AlphaRisk):
    """
    Isolated V11.30 crash-rebound observation lane.

    The parent strategy supplies existing indicators and alpha-risk telemetry.
    This class clears inherited entries and emits only the V11.30 shadow tag.
    """

    can_short = False
    timeframe = "15m"
    position_adjustment_enable = False
    max_entry_position_adjustment = 0

    minimal_roi = {
        "0": 0.012,
        "60": 0.008,
        "120": 0.004,
        "240": 0,
    }
    stoploss = -0.02

    trade_supervisor_bot_key = os.getenv("TRADE_SUPERVISOR_BOT_KEY", "v1130_crash_rebound_shadow")
    scale_in_tag_prefix = "v1130"

    shadow_entry_tag = "v1130_crash_rebound_long"
    shadow_stake_amount = 250
    shadow_allowed_pairs = {
        "ETH/USDT:USDT",
        "SOL/USDT:USDT",
        "DOGE/USDT:USDT",
        "LINK/USDT:USDT",
        "XRP/USDT:USDT",
        "BCH/USDT:USDT",
    }

    shadow_min_15m_return = 0.004
    shadow_min_15m_range = 0.012
    shadow_min_rsi = 35
    shadow_max_rsi = 62
    shadow_min_volume_ratio = 0.8
    shadow_take_profit = 0.008
    shadow_overbought_rsi = 68
    shadow_time_exit_minutes = 120
    final_decision_telemetry_json = "reports/v1130_observation/v1130_final_decision_telemetry.json"
    final_decision_telemetry_md = "reports/v1130_observation/v1130_final_decision_telemetry.md"

    raw_required_columns = [
        "open",
        "high",
        "low",
        "close",
        "volume",
        "volume_mean",
        "rsi",
    ]
    alpha_required_columns = [
        "alpha_filter_block_short",
        "alpha_risk_flags",
    ]

    def populate_entry_trend(self, dataframe: DataFrame, metadata: dict) -> DataFrame:
        dataframe = dataframe.copy()
        pair = metadata.get("pair", "")
        self._reset_v1130_entries(dataframe)

        raw_missing = self._missing_columns(dataframe, self.raw_required_columns)
        if raw_missing:
            dataframe["v1130_crash_rebound_gate"] = "blocked_missing_columns:" + ",".join(raw_missing)
            self._record_final_decision_telemetry(dataframe, metadata)
            return dataframe

        dataframe = super().populate_entry_trend(dataframe, metadata)
        self._reset_v1130_entries(dataframe)

        if pair not in self.shadow_allowed_pairs:
            dataframe["v1130_crash_rebound_gate"] = "blocked_pair_not_allowlisted"
            self._record_final_decision_telemetry(dataframe, metadata)
            return dataframe

        alpha_missing = self._missing_columns(dataframe, self.alpha_required_columns)
        if alpha_missing:
            dataframe["v1130_crash_rebound_gate"] = "blocked_missing_columns:" + ",".join(alpha_missing)
            self._record_final_decision_telemetry(dataframe, metadata)
            return dataframe

        candidate = self._crash_rebound_candidate(dataframe)
        alpha_short_blocked = dataframe["alpha_filter_block_short"].fillna(True).astype(bool)
        taker_sell_pressure = dataframe["alpha_risk_flags"].map(self._has_taker_sell_pressure)

        dataframe.loc[
            candidate & taker_sell_pressure,
            "v1130_crash_rebound_gate",
        ] = "blocked_taker_sell_pressure"
        dataframe.loc[candidate & alpha_short_blocked & ~taker_sell_pressure, "v1130_crash_rebound_gate"] = "blocked_alpha_short"

        enabled = candidate & ~alpha_short_blocked & ~taker_sell_pressure
        dataframe.loc[enabled, "enter_long"] = 1
        dataframe.loc[enabled, "enter_tag"] = self.shadow_entry_tag
        dataframe.loc[enabled, "v1130_crash_rebound_gate"] = "enabled_crash_rebound_long"

        self._record_final_decision_telemetry(dataframe, metadata, candidate, taker_sell_pressure)
        return dataframe

    def custom_stake_amount(
        self,
        pair: str,
        current_time,
        current_rate: float,
        proposed_stake: float,
        min_stake: float | None,
        max_stake: float,
        leverage: float,
        entry_tag: str | None,
        side: str,
        **kwargs,
    ) -> float:
        if side == "long" and entry_tag == self.shadow_entry_tag:
            return self._capped_stake(self.shadow_stake_amount, proposed_stake, min_stake, max_stake)

        return super().custom_stake_amount(
            pair=pair,
            current_time=current_time,
            current_rate=current_rate,
            proposed_stake=proposed_stake,
            min_stake=min_stake,
            max_stake=max_stake,
            leverage=leverage,
            entry_tag=entry_tag,
            side=side,
            **kwargs,
        )

    def custom_exit(
        self,
        pair: str,
        trade,
        current_time,
        current_rate: float,
        current_profit: float,
        **kwargs,
    ):
        if getattr(trade, "enter_tag", None) == self.shadow_entry_tag:
            if current_profit >= self.shadow_take_profit:
                return "v1130_rebound_take_profit"

            last = self._last_analyzed_candle(pair)
            if last is not None and self._finite_float(last.get("rsi")) is not None:
                if self._finite_float(last.get("rsi")) > self.shadow_overbought_rsi:
                    return "v1130_rebound_rsi_exit"

            if current_time - trade.open_date_utc >= timedelta(minutes=self.shadow_time_exit_minutes):
                return "v1130_rebound_time_exit"
            return None

        return super().custom_exit(pair, trade, current_time, current_rate, current_profit, **kwargs)

    def _crash_rebound_candidate(self, dataframe: DataFrame):
        candle_return = (dataframe["close"] - dataframe["open"]) / dataframe["open"].where(dataframe["open"] != 0)
        candle_range = (dataframe["high"] - dataframe["low"]) / dataframe["close"].where(dataframe["close"] != 0)
        volume_ok = dataframe["volume"] > dataframe["volume_mean"] * self.shadow_min_volume_ratio

        return (
            (candle_return > self.shadow_min_15m_return)
            & (candle_range >= self.shadow_min_15m_range)
            & (dataframe["rsi"] >= self.shadow_min_rsi)
            & (dataframe["rsi"] <= self.shadow_max_rsi)
            & volume_ok
            & (dataframe["volume"] > 0)
        )

    @staticmethod
    def _reset_v1130_entries(dataframe: DataFrame) -> None:
        dataframe["enter_long"] = 0
        dataframe["enter_short"] = 0
        dataframe["enter_tag"] = ""
        dataframe["v1130_crash_rebound_gate"] = "not_candidate"

    @staticmethod
    def _missing_columns(dataframe: DataFrame, columns: list[str]) -> list[str]:
        return [column for column in columns if column not in dataframe.columns]

    @staticmethod
    def _has_taker_sell_pressure(raw_flags) -> bool:
        flags = {flag for flag in str(raw_flags or "").split(",") if flag}
        return "takerSellPressure" in flags

    @staticmethod
    def _capped_stake(target_stake: float, proposed_stake: float, min_stake: float | None, max_stake: float) -> float:
        stake = min(target_stake, proposed_stake, max_stake)
        if min_stake is not None and stake < min_stake:
            return min(max_stake, proposed_stake)
        return stake

    def _last_analyzed_candle(self, pair: str):
        if not getattr(self, "dp", None):
            return None
        dataframe, _ = self.dp.get_analyzed_dataframe(pair, self.timeframe)
        if dataframe.empty:
            return None
        return dataframe.iloc[-1]

    def _record_final_decision_telemetry(self, dataframe: DataFrame, metadata: dict, candidate=None, taker_sell_pressure=None) -> None:
        if os.getenv("V1130_FINAL_DECISION_TELEMETRY_DISABLE") == "1":
            return

        try:
            json_path = self._telemetry_path(
                os.getenv("V1130_FINAL_DECISION_TELEMETRY_JSON"),
                self.final_decision_telemetry_json,
            )
            md_path = self._telemetry_path(
                os.getenv("V1130_FINAL_DECISION_TELEMETRY_MD"),
                self.final_decision_telemetry_md,
            )
            report = self._build_final_decision_telemetry_report(dataframe, metadata, candidate, taker_sell_pressure)
            report = self._merge_final_decision_telemetry_report(json_path, report)
            json_path.parent.mkdir(parents=True, exist_ok=True)
            md_path.parent.mkdir(parents=True, exist_ok=True)
            json_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            md_path.write_text(self._format_final_decision_telemetry_markdown(report), encoding="utf-8")
        except Exception:
            return

    @staticmethod
    def _merge_final_decision_telemetry_report(json_path: Path, pair_report: dict) -> dict:
        pair = pair_report["metadata"]["pair"]
        pairs = {}
        if json_path.exists():
            try:
                existing = json.loads(json_path.read_text(encoding="utf-8"))
                pairs = existing.get("pairs", {}) if isinstance(existing.get("pairs"), dict) else {}
            except Exception:
                pairs = {}
        pairs[pair] = pair_report
        return {
            "metadata": {
                "strategy": pair_report["metadata"]["strategy"],
                "timeframe": pair_report["metadata"]["timeframe"],
                "generated_at": pair_report["metadata"]["generated_at"],
                "source": pair_report["metadata"]["source"],
                "behavior": pair_report["metadata"]["behavior"],
                "latest_updated_pair": pair,
            },
            "pairs": pairs,
            "summary": {
                "pairs_observed": len(pairs),
                "rows_observed": sum(item.get("summary", {}).get("rows_observed", 0) for item in pairs.values()),
                "candidate_rows": sum(item.get("summary", {}).get("candidate_rows", 0) for item in pairs.values()),
                "enabled_rows": sum(item.get("summary", {}).get("enabled_rows", 0) for item in pairs.values()),
                "blocked_rows": sum(item.get("summary", {}).get("blocked_rows", 0) for item in pairs.values()),
            },
            "data_gaps": sorted({gap for item in pairs.values() for gap in item.get("data_gaps", [])}),
            "safety_verdict": "telemetry_only_no_behavior_change",
        }

    @staticmethod
    def _telemetry_path(configured: str | None, default: str) -> Path:
        raw_path = configured or default
        path = Path(raw_path)
        if path.is_absolute():
            return path
        return Path.cwd() / path

    def _build_final_decision_telemetry_report(self, dataframe: DataFrame, metadata: dict, candidate=None, taker_sell_pressure=None) -> dict:
        rows = self._telemetry_rows(dataframe, metadata.get("pair", "unknown"), candidate, taker_sell_pressure)
        latest_rows = rows[-6:]
        candidate_rows = [row for row in rows if row["candidate"]["value"] is True]
        enabled_rows = [row for row in rows if row["v1130_crash_rebound_gate"]["value"] == "enabled_crash_rebound_long"]
        blocked_rows = [
            row for row in rows
            if isinstance(row["v1130_crash_rebound_gate"]["value"], str)
            and row["v1130_crash_rebound_gate"]["value"].startswith("blocked_")
        ]
        return {
            "metadata": {
                "strategy": self.__class__.__name__,
                "timeframe": self.timeframe,
                "pair": metadata.get("pair", "unknown"),
                "generated_at": self._utc_now_iso(),
                "source": "strategy_populate_entry_trend",
                "behavior": "telemetry_only_no_behavior_change",
            },
            "runtime_context": {
                "shadow_entry_tag": self.shadow_entry_tag,
                "allowed_pair": metadata.get("pair", "") in self.shadow_allowed_pairs,
            },
            "latest_rows": latest_rows,
            "candidate_rows": candidate_rows[-20:],
            "enabled_rows": enabled_rows[-20:],
            "blocked_rows": blocked_rows[-20:],
            "summary": {
                "rows_observed": len(rows),
                "candidate_rows": len(candidate_rows),
                "enabled_rows": len(enabled_rows),
                "blocked_rows": len(blocked_rows),
            },
            "data_gaps": self._telemetry_data_gaps(rows),
            "safety_verdict": "telemetry_only_no_behavior_change",
        }

    def _telemetry_rows(self, dataframe: DataFrame, pair: str, candidate=None, taker_sell_pressure=None) -> list[dict]:
        rows = []
        candidate_values = self._series_values(candidate, len(dataframe))
        taker_values = self._series_values(taker_sell_pressure, len(dataframe))
        for index, (_, row) in enumerate(dataframe.tail(50).iterrows()):
            candidate_value = candidate_values[index] if candidate_values is not None else self._candidate_value(row)
            taker_value = taker_values[index] if taker_values is not None else self._taker_pressure_value(row)
            rows.append({
                "pair": self._field("observed", pair),
                "timeframe": self._field("observed", self.timeframe),
                "candle_time": self._field_from_row(row, "date"),
                "open": self._field_from_row(row, "open"),
                "high": self._field_from_row(row, "high"),
                "low": self._field_from_row(row, "low"),
                "close": self._field_from_row(row, "close"),
                "volume": self._field_from_row(row, "volume"),
                "candle_return": self._derived_ratio(row, "close", "open", subtract_one=True),
                "candle_range": self._derived_range(row),
                "rsi": self._field_from_row(row, "rsi"),
                "volume_ratio": self._volume_ratio(row),
                "candidate": self._field(candidate_value[0], candidate_value[1]),
                "alpha_filter_block_short": self._field_from_row(row, "alpha_filter_block_short"),
                "alpha_risk_flags": self._field_from_row(row, "alpha_risk_flags"),
                "taker_sell_pressure": self._field(taker_value[0], taker_value[1]),
                "v1130_crash_rebound_gate": self._field_from_row(row, "v1130_crash_rebound_gate"),
                "enter_long": self._field_from_row(row, "enter_long"),
                "enter_tag": self._field_from_row(row, "enter_tag"),
            })
        return rows

    @staticmethod
    def _series_values(series, length: int):
        if series is None:
            return None
        values = list(series.tail(50)) if hasattr(series, "tail") else list(series)[-50:]
        return [("derived", bool(value)) for value in values[-min(50, length):]]

    def _candidate_value(self, row):
        required = ["open", "high", "low", "close", "volume", "volume_mean", "rsi"]
        if any(column not in row.index for column in required):
            return "missing", None
        try:
            candle_return = (float(row["close"]) - float(row["open"])) / float(row["open"])
            candle_range = (float(row["high"]) - float(row["low"])) / float(row["close"])
            volume_ok = float(row["volume"]) > float(row["volume_mean"]) * self.shadow_min_volume_ratio
            return "derived", (
                candle_return > self.shadow_min_15m_return
                and candle_range >= self.shadow_min_15m_range
                and float(row["rsi"]) >= self.shadow_min_rsi
                and float(row["rsi"]) <= self.shadow_max_rsi
                and volume_ok
                and float(row["volume"]) > 0
            )
        except Exception:
            return "unknown", None

    def _taker_pressure_value(self, row):
        if "alpha_risk_flags" not in row.index:
            return "missing", None
        return "derived", self._has_taker_sell_pressure(row.get("alpha_risk_flags"))

    @staticmethod
    def _field_from_row(row, column: str) -> dict:
        if column not in row.index:
            return {"state": "missing", "value": None}
        return {"state": "observed", "value": RegimeAwareV1130CrashReboundShadow._json_value(row.get(column))}

    @staticmethod
    def _field(state: str, value) -> dict:
        return {"state": state, "value": RegimeAwareV1130CrashReboundShadow._json_value(value)}

    @staticmethod
    def _json_value(value):
        if hasattr(value, "isoformat"):
            return value.isoformat()
        if hasattr(value, "item"):
            return value.item()
        return value

    @staticmethod
    def _derived_ratio(row, numerator: str, denominator: str, subtract_one: bool = False) -> dict:
        if numerator not in row.index or denominator not in row.index:
            return {"state": "missing", "value": None}
        try:
            base = float(row[denominator])
            if base == 0:
                return {"state": "unknown", "value": None}
            value = float(row[numerator]) / base
            return {"state": "derived", "value": value - 1 if subtract_one else value}
        except Exception:
            return {"state": "unknown", "value": None}

    @staticmethod
    def _derived_range(row) -> dict:
        if "high" not in row.index or "low" not in row.index or "close" not in row.index:
            return {"state": "missing", "value": None}
        try:
            close = float(row["close"])
            if close == 0:
                return {"state": "unknown", "value": None}
            return {"state": "derived", "value": (float(row["high"]) - float(row["low"])) / close}
        except Exception:
            return {"state": "unknown", "value": None}

    @staticmethod
    def _volume_ratio(row) -> dict:
        if "volume" not in row.index or "volume_mean" not in row.index:
            return {"state": "missing", "value": None}
        try:
            mean = float(row["volume_mean"])
            if mean == 0:
                return {"state": "unknown", "value": None}
            return {"state": "derived", "value": float(row["volume"]) / mean}
        except Exception:
            return {"state": "unknown", "value": None}

    @staticmethod
    def _telemetry_data_gaps(rows: list[dict]) -> list[str]:
        gaps = set()
        for row in rows:
            for key, field in row.items():
                if isinstance(field, dict) and field.get("state") in {"missing", "unknown"}:
                    gaps.add(key)
        return sorted(gaps)

    @staticmethod
    def _format_final_decision_telemetry_markdown(report: dict) -> str:
        summary = report["summary"]
        metadata = report["metadata"]
        latest_pair = metadata.get("latest_updated_pair", "unknown")
        latest_report = report.get("pairs", {}).get(latest_pair, {})
        latest_rows = latest_report.get("latest_rows", [])
        return "\n".join([
            "# V11.30 Final Decision Telemetry",
            "",
            "## Summary",
            "",
            f"- strategy: `{metadata['strategy']}`",
            f"- latest_updated_pair: `{latest_pair}`",
            f"- timeframe: `{metadata['timeframe']}`",
            f"- generated_at: `{metadata['generated_at']}`",
            f"- safety_verdict: `{report['safety_verdict']}`",
            f"- pairs_observed: `{summary['pairs_observed']}`",
            f"- rows_observed: `{summary['rows_observed']}`",
            f"- candidate_rows: `{summary['candidate_rows']}`",
            f"- enabled_rows: `{summary['enabled_rows']}`",
            f"- blocked_rows: `{summary['blocked_rows']}`",
            "",
            "## Latest Rows",
            "",
            "| candle_time | candidate | gate | enter_long | enter_tag |",
            "|---|---:|---|---:|---|",
            *[
                "| {time} | {candidate} | {gate} | {enter_long} | {enter_tag} |".format(
                    time=row["candle_time"]["value"],
                    candidate=row["candidate"]["value"],
                    gate=row["v1130_crash_rebound_gate"]["value"],
                    enter_long=row["enter_long"]["value"],
                    enter_tag=row["enter_tag"]["value"],
                )
                for row in latest_rows
            ],
            "",
            "## Data Gaps",
            "",
            "\n".join(f"- `{gap}`" for gap in report["data_gaps"]) if report["data_gaps"] else "- none observed",
            "",
            "## Safety Boundary",
            "",
            "This telemetry mirrors final strategy decision fields only. It does not approve V11.30 replacement readiness.",
            "",
        ])

    @staticmethod
    def _utc_now_iso() -> str:
        from datetime import datetime, timezone

        return datetime.now(timezone.utc).isoformat()
