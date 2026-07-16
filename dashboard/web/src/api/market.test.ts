import { describe, expect, it } from "vitest";

import { assertMarketResponse } from "./market";

describe("assertMarketResponse", () => {
  it("accepts real OHLC candles", () => {
    expect(() => assertMarketResponse({
      pair: "BTC/USDT:USDT",
      candles: [{ time: 1, open: 10, high: 12, low: 9, close: 11 }],
    })).not.toThrow();
  });

  it("rejects incomplete candles instead of drawing them", () => {
    expect(() => assertMarketResponse({ pair: "BTC/USDT:USDT", candles: [{ time: 1, close: 11 }] })).toThrow(
      "market_response_invalid:candles",
    );
  });
});
