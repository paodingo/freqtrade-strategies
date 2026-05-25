"""Market regime detection using 4h data with majority voting and hysteresis."""
import pandas as pd
import talib.abstract as ta


class RegimeDetector:
    TRENDING = "trending"
    RANGING = "ranging"

    def __init__(
        self,
        adx_trend_threshold: int = 25,
        adx_range_threshold: int = 20,
        confirmation_candles: int = 3,
    ):
        self.adx_trend_threshold = adx_trend_threshold
        self.adx_range_threshold = adx_range_threshold
        self.confirmation_candles = confirmation_candles
        self._current_regime = self.RANGING
        self._signal_buffer = []

    def compute_indicators(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        """Add regime-related indicators to a 4h dataframe."""
        df = dataframe.copy()

        df["adx"] = ta.ADX(df, timeperiod=14)

        bb = ta.BBANDS(df, timeperiod=20, nbdevup=2.0, nbdevdn=2.0)
        df["bb_upper"] = bb["upperband"]
        df["bb_middle"] = bb["middleband"]
        df["bb_lower"] = bb["lowerband"]
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / df["bb_middle"]
        df["bb_width_mean"] = df["bb_width"].rolling(50).mean()

        df["atr"] = ta.ATR(df, timeperiod=14)
        df["atr_mean"] = df["atr"].rolling(50).mean()

        return df

    def detect(self, dataframe_4h: pd.DataFrame) -> str:
        """Run regime detection on 4h dataframe with indicators already computed.
        Returns TRENDING or RANGING.
        """
        latest = dataframe_4h.iloc[-1]

        adx = latest.get("adx", 20)
        bb_width = latest.get("bb_width", 0)
        bb_width_mean = latest.get("bb_width_mean", 1)
        atr_val = latest.get("atr", 0)
        atr_mean = latest.get("atr_mean", 1)

        # Vote 1: ADX
        if adx > self.adx_trend_threshold:
            adx_vote = self.TRENDING
        elif adx < self.adx_range_threshold:
            adx_vote = self.RANGING
        else:
            adx_vote = None  # 20-25 grey zone

        # Vote 2: BB width (expanding = trending, contracting = ranging)
        if bb_width_mean > 0:
            bb_vote = (
                self.TRENDING if (bb_width / bb_width_mean) > 1.0 else self.RANGING
            )
        else:
            bb_vote = None

        # Vote 3: ATR (above mean = high vol/trending, below = ranging)
        if atr_mean > 0:
            atr_vote = self.TRENDING if atr_val > atr_mean else self.RANGING
        else:
            atr_vote = None

        trending_votes = sum(
            1 for v in [adx_vote, bb_vote, atr_vote] if v == self.TRENDING
        )
        ranging_votes = sum(
            1 for v in [adx_vote, bb_vote, atr_vote] if v == self.RANGING
        )

        # 2/3 majority voting (unanimity is too strict for real markets)
        if trending_votes >= 2:
            signal = self.TRENDING
        elif ranging_votes >= 2:
            signal = self.RANGING
        else:
            signal = None  # genuine deadlock (e.g., 1T/1R/1? or all None)

        # Hysteresis: require N consecutive identical signals to switch
        if signal is not None:
            self._signal_buffer.append(signal)
            if len(self._signal_buffer) > self.confirmation_candles:
                self._signal_buffer.pop(0)
            if len(self._signal_buffer) == self.confirmation_candles and all(
                s == signal for s in self._signal_buffer
            ):
                self._current_regime = signal
        # If ambiguous, maintain current regime and keep buffer (don't reset)

        return self._current_regime

    def is_trending(self) -> bool:
        return self._current_regime == self.TRENDING

    def is_ranging(self) -> bool:
        return self._current_regime == self.RANGING

    def reset(self):
        self._current_regime = self.RANGING
        self._signal_buffer = []
