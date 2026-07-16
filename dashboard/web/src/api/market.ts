export type MarketTimeframe = "5m" | "15m" | "1h" | "4h";

export interface CandlePoint {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface MarketResponse {
  generatedAt: string;
  pair: string;
  timeframe: MarketTimeframe;
  sourceBot: string;
  sourceType: string;
  fallback: boolean;
  candles: CandlePoint[];
  ticker: {
    symbol: string;
    price: number;
    updatedAt: string;
    source: string;
  } | null;
  lastAnalyzed: string | null;
  dataFreshness: {
    ageSeconds: number | null;
    staleSeconds: number;
    stale: boolean;
  };
}

function isFiniteNumber(value: unknown): value is number {
  return typeof value === "number" && Number.isFinite(value);
}

export function assertMarketResponse(value: unknown): asserts value is MarketResponse {
  if (!value || typeof value !== "object") throw new Error("market_response_invalid:document");
  const response = value as Partial<MarketResponse>;
  if (typeof response.pair !== "string" || !Array.isArray(response.candles)) {
    throw new Error("market_response_invalid:shape");
  }
  if (response.candles.some((candle) => !candle || !isFiniteNumber(candle.time)
    || !isFiniteNumber(candle.open) || !isFiniteNumber(candle.high)
    || !isFiniteNumber(candle.low) || !isFiniteNumber(candle.close))) {
    throw new Error("market_response_invalid:candles");
  }
}

export async function fetchMarketContext(timeframe: MarketTimeframe, signal?: AbortSignal): Promise<MarketResponse> {
  const query = new URLSearchParams({ timeframe, limit: "120" });
  const response = await fetch(`/api/market?${query.toString()}`, {
    cache: "no-store",
    headers: { Accept: "application/json" },
    signal,
  });
  if (!response.ok) throw new Error(`market_request_failed:${response.status}`);
  const payload: unknown = await response.json();
  assertMarketResponse(payload);
  return payload;
}
