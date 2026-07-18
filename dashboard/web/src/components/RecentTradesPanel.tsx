import { useQuery } from "@tanstack/react-query";

import { fetchTrades } from "../api/trades";
import { formatMoney, formatPercent, valueTone } from "../lib/format";

function formatTradeTime(timestamp: number | null): string {
  if (!timestamp || !Number.isFinite(timestamp)) return "—";
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(new Date(timestamp));
}

export function RecentTradesPanel() {
  const query = useQuery({
    queryKey: ["closed-trades", "v1", 20],
    queryFn: ({ signal }) => fetchTrades(signal, 20),
    staleTime: 10_000,
    refetchInterval: 15_000,
    refetchOnWindowFocus: true,
    retry: 1,
  });
  const trades = query.data?.trades || [];

  return (
    <section className="recent-trades-panel" aria-labelledby="recent-trades-title">
      <div className="section-copy horizontal">
        <div>
          <p className="eyebrow">EXECUTION LEDGER</p>
          <h2 id="recent-trades-title">最近交易与决策理由</h2>
        </div>
        <p>每笔交易同时保留入场标签、退出原因、实际盈亏和时间，避免“有成交但没人知道”。</p>
      </div>

      {query.isPending ? <p className="trade-ledger-state">正在读取交易账本…</p> : null}
      {query.isError ? <p className="trade-ledger-state error">交易账本暂时不可用。</p> : null}
      {!query.isPending && !query.isError && trades.length === 0 ? (
        <p className="trade-ledger-state">当前运行策略尚无已平仓交易。</p>
      ) : null}

      {trades.length > 0 ? (
        <div className="trade-ledger-wrap">
          <table className="trade-ledger-table">
            <thead>
              <tr>
                <th>策略 / 时间</th>
                <th>交易</th>
                <th>为什么入场</th>
                <th>为什么退出</th>
                <th>结果</th>
              </tr>
            </thead>
            <tbody>
              {trades.map((trade) => (
                <tr key={`${trade.botKey}-${trade.tradeId ?? `${trade.pair}-${trade.closeTimestamp}`}`}>
                  <td>
                    <strong>{trade.botLabel}</strong>
                    <small>{formatTradeTime(trade.closeTimestamp)}</small>
                  </td>
                  <td>
                    <strong>{trade.isShort ? "做空" : "做多"} {trade.pair}</strong>
                    <small>{trade.openRate ?? "—"} → {trade.closeRate ?? "—"}</small>
                  </td>
                  <td>
                    <strong>{trade.signalText || trade.enterTag || "未记录"}</strong>
                    <small>{trade.enterTag || "无 enter_tag"}</small>
                  </td>
                  <td>
                    <strong>{trade.exitReasonText || trade.exitReason || "未记录"}</strong>
                    <small>{trade.exitReason || "无 exit_reason"}</small>
                  </td>
                  <td>
                    <strong className={`value-${valueTone(trade.realizedProfit)}`}>
                      {formatMoney(trade.realizedProfit)}
                    </strong>
                    <small>{formatPercent(trade.realizedProfitRatio)}</small>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </section>
  );
}
