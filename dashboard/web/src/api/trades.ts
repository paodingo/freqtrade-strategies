export interface ClosedTradeRecord {
  botKey: string;
  botLabel: string;
  tradeId: number | string | null;
  pair: string;
  isShort: boolean;
  enterTag: string | null;
  signalText: string;
  exitReason: string | null;
  exitReasonText: string;
  openRate: number | null;
  closeRate: number | null;
  realizedProfit: number;
  realizedProfitRatio: number | null;
  stakeAmount: number | null;
  feeOpenCost: number;
  feeCloseCost: number;
  openTimestamp: number | null;
  closeTimestamp: number;
  openDate: string | null;
  closeDate: string | null;
}

export interface TradesResponse {
  generatedAt: string;
  limit: number;
  trades: ClosedTradeRecord[];
}

export function assertTradesResponse(value: unknown): asserts value is TradesResponse {
  if (!value || typeof value !== "object") throw new Error("trades_response_invalid:document");
  const response = value as Partial<TradesResponse>;
  if (!Array.isArray(response.trades)) throw new Error("trades_response_invalid:trades");
  for (const trade of response.trades) {
    if (!trade || typeof trade !== "object" || !trade.pair || !trade.closeTimestamp) {
      throw new Error("trades_response_invalid:trade");
    }
  }
}

export async function fetchTrades(signal?: AbortSignal, limit = 20): Promise<TradesResponse> {
  const response = await fetch(`/api/trades?limit=${limit}`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) throw new Error(`trades_request_failed:${response.status}`);
  const payload: unknown = await response.json();
  assertTradesResponse(payload);
  return {
    ...payload,
    trades: [...payload.trades].sort((left, right) => right.closeTimestamp - left.closeTimestamp),
  };
}
