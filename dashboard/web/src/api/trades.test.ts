import { describe, expect, it } from "vitest";

import { assertTradesResponse } from "./trades";

describe("assertTradesResponse", () => {
  it("accepts closed trade records with reasons", () => {
    expect(() => assertTradesResponse({
      generatedAt: "2026-07-18T00:00:00Z",
      limit: 20,
      trades: [{ pair: "ETH/USDT:USDT", closeTimestamp: 1, signalText: "暴跌反弹做多" }],
    })).not.toThrow();
  });

  it("rejects records without a close timestamp", () => {
    expect(() => assertTradesResponse({ trades: [{ pair: "ETH/USDT:USDT" }] })).toThrow(
      "trades_response_invalid:trade",
    );
  });
});
