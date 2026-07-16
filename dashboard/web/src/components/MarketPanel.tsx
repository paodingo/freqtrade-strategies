import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchMarketContext, type CandlePoint, type MarketTimeframe } from "../api/market";
import { formatAge, valueTone } from "../lib/format";

interface SeriesApi {
  setData: (data: CandlePoint[]) => void;
}

interface ChartApi {
  addSeries: (definition: unknown, options: Record<string, unknown>) => SeriesApi;
  applyOptions: (options: Record<string, unknown>) => void;
  remove: () => void;
  timeScale: () => { fitContent: () => void };
}

interface LightweightChartsApi {
  CandlestickSeries: unknown;
  createChart: (element: HTMLElement, options: Record<string, unknown>) => ChartApi;
}

declare global {
  interface Window {
    LightweightCharts?: LightweightChartsApi;
  }
}

let chartLibraryPromise: Promise<LightweightChartsApi> | null = null;

function loadChartLibrary(): Promise<LightweightChartsApi> {
  if (window.LightweightCharts) return Promise.resolve(window.LightweightCharts);
  if (chartLibraryPromise) return chartLibraryPromise;
  chartLibraryPromise = new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = "/vendor/lightweight-charts/lightweight-charts.standalone.production.js";
    script.async = true;
    script.onload = () => window.LightweightCharts
      ? resolve(window.LightweightCharts)
      : reject(new Error("chart_library_global_missing"));
    script.onerror = () => reject(new Error("chart_library_load_failed"));
    document.head.append(script);
  });
  return chartLibraryPromise;
}

function priceText(value: number | null): string {
  if (value === null || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(value);
}

export function MarketPanel() {
  const [timeframe, setTimeframe] = useState<MarketTimeframe>("15m");
  const [chartError, setChartError] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const seriesRef = useRef<SeriesApi | null>(null);
  const query = useQuery({
    queryKey: ["market-context", timeframe],
    queryFn: ({ signal }) => fetchMarketContext(timeframe, signal),
    staleTime: 10_000,
    refetchInterval: 15_000,
    retry: 1,
  });
  const data = query.data;
  const candlesRef = useRef<CandlePoint[]>([]);
  const hasCandles = Boolean(data?.candles.length);
  const latestClose = data?.candles.at(-1)?.close ?? null;
  const currentPrice = data?.ticker?.price ?? latestClose;
  const firstClose = data?.candles.at(0)?.close ?? null;
  const changePct = currentPrice !== null && firstClose !== null && firstClose !== 0
    ? ((currentPrice - firstClose) / firstClose) * 100
    : null;

  useEffect(() => {
    candlesRef.current = data?.candles ?? [];
    if (seriesRef.current) seriesRef.current.setData(candlesRef.current);
  }, [data?.candles]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || !data?.timeframe || !hasCandles) return undefined;
    let disposed = false;
    let chart: ChartApi | null = null;
    let observer: ResizeObserver | null = null;
    setChartError(false);
    void loadChartLibrary().then((library) => {
      if (disposed) return;
      chart = library.createChart(container, {
        width: Math.max(1, container.clientWidth),
        height: Math.max(320, container.clientHeight),
        layout: {
          background: { color: "transparent" },
          textColor: "#91a8a5",
          fontFamily: "JetBrains Mono Variable, monospace",
          fontSize: 11,
        },
        grid: {
          vertLines: { color: "rgba(116, 145, 142, 0.14)" },
          horzLines: { color: "rgba(116, 145, 142, 0.14)" },
        },
        rightPriceScale: { borderColor: "rgba(116, 145, 142, 0.28)" },
        timeScale: { borderColor: "rgba(116, 145, 142, 0.28)", timeVisible: true },
      });
      const series = chart.addSeries(library.CandlestickSeries, {
        upColor: "#20d39a",
        downColor: "#ff5d73",
        borderVisible: false,
        wickUpColor: "#20d39a",
        wickDownColor: "#ff5d73",
      });
      seriesRef.current = series;
      series.setData(candlesRef.current);
      chart.timeScale().fitContent();
      observer = new ResizeObserver(() => chart?.applyOptions({ width: Math.max(1, container.clientWidth) }));
      observer.observe(container);
    }).catch(() => setChartError(true));
    return () => {
      disposed = true;
      observer?.disconnect();
      chart?.remove();
      seriesRef.current = null;
    };
  }, [data?.timeframe, hasCandles]);

  return (
    <section className="market-panel" aria-labelledby="market-panel-title">
      <div className="market-heading">
        <div>
          <p className="eyebrow">MARKET CONTEXT / REAL OHLCV</p>
          <h2 id="market-panel-title">{data?.pair || "当前交易对"}</h2>
          <p>真实 K 线用于理解价格走向，不代表策略会据此自动下单。</p>
        </div>
        <div className="market-quote" aria-label="当前币种价格">
          <span>当前价</span>
          <strong>{priceText(currentPrice)}</strong>
          <small className={`value-${valueTone(changePct)}`}>
            {changePct === null ? "区间变化 —" : `近 ${data?.candles.length ?? 0} 根 ${changePct > 0 ? "+" : ""}${changePct.toFixed(2)}%`}
          </small>
        </div>
      </div>
      <div className="timeframe-switch" aria-label="K 线周期">
        {(["5m", "15m", "1h", "4h"] as const).map((item) => (
          <button key={item} type="button" className={timeframe === item ? "active" : ""} onClick={() => setTimeframe(item)}>
            {item}
          </button>
        ))}
      </div>
      <div className="chart-frame">
        {query.isPending ? <div className="chart-state">正在读取真实 OHLCV…</div> : null}
        {query.isError ? <div className="chart-state error">K 线数据暂时不可用；不会绘制替代走势。</div> : null}
        {data && data.candles.length === 0 ? <div className="chart-state">当前周期没有可绘制的 K 线。</div> : null}
        {chartError ? <div className="chart-state error">本地图表组件加载失败。</div> : null}
        <div ref={containerRef} className="market-chart" aria-label={`${data?.pair || "当前交易对"} ${timeframe} K 线`} />
      </div>
      {data ? (
        <div className="market-meta">
          <span>来源 {data.sourceBot}</span>
          <span>{data.fallback ? "交易所回退数据" : data.sourceType}</span>
          <span className={data.dataFreshness.stale ? "value-negative" : ""}>更新 {formatAge(data.dataFreshness.ageSeconds)}</span>
        </div>
      ) : null}
    </section>
  );
}
