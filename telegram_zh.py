"""
Freqtrade Telegram 中文消息钩子
通过 webhook 方式，在策略层面发送中文通知
"""
import logging
from freqtrade.strategy import IStrategy
from freqtrade.persistence import Trade

logger = logging.getLogger(__name__)


class TelegramZhMixin:
    """
    混入类：在策略中添加中文 Telegram 通知
    在你的策略类中继承这个 mixin 即可
    """

    def confirm_trade_entry(self, pair, order_type, amount, rate, time_in_force, 
                            current_time, entry_tag, side, **kwargs) -> bool:
        """买入确认 - 记录日志（freqtrade 会自动发 Telegram）"""
        logger.info(f"📈 准备买入 {pair}，价格 {rate:.2f}，数量 {amount:.6f}")
        return True

    def confirm_trade_exit(self, pair, trade: Trade, order_type, amount, rate,
                           time_in_force, exit_reason, current_time, **kwargs) -> bool:
        """卖出确认"""
        profit_pct = trade.calc_profit_ratio(rate) * 100
        emoji = "🟢" if profit_pct > 0 else "🔴"
        logger.info(f"{emoji} 准备卖出 {pair}，收益 {profit_pct:.2f}%，原因：{exit_reason}")
        return True
