"use client";
import { useEffect, useRef } from "react";
import { createChart, CandlestickSeries, HistogramSeries, LineSeries } from "lightweight-charts";

interface Bar {
  time: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export function CandlestickChart({ bars }: { bars: Bar[] }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!containerRef.current || bars.length === 0) return;

    const chart = createChart(containerRef.current, {
      layout: { background: { color: "#0f1117" }, textColor: "#9ca3af" },
      grid: { vertLines: { color: "#1f2937" }, horzLines: { color: "#1f2937" } },
      width: containerRef.current.clientWidth,
      height: 400,
      timeScale: { borderColor: "#2d3148" },
      rightPriceScale: { borderColor: "#2d3148" },
    });

    // Candlestick
    const candleSeries = chart.addSeries(CandlestickSeries, {
      upColor: "#10b981",
      downColor: "#ef4444",
      borderUpColor: "#10b981",
      borderDownColor: "#ef4444",
      wickUpColor: "#10b981",
      wickDownColor: "#ef4444",
    });
    candleSeries.setData(bars.map((b) => ({
      time: b.time as any,
      open: b.open,
      high: b.high,
      low: b.low,
      close: b.close,
    })));

    // Volume
    const volumeSeries = chart.addSeries(HistogramSeries, {
      priceFormat: { type: "volume" },
      priceScaleId: "volume",
    });
    chart.priceScale("volume").applyOptions({ scaleMargins: { top: 0.8, bottom: 0 } });
    volumeSeries.setData(bars.map((b) => ({
      time: b.time as any,
      value: b.volume,
      color: b.close >= b.open ? "rgba(16,185,129,0.3)" : "rgba(239,68,68,0.3)",
    })));

    // MA5
    if (bars.length >= 5) {
      const ma5 = chart.addSeries(LineSeries, { color: "#f59e0b", lineWidth: 1, priceLineVisible: false });
      const ma5Data = bars.map((_, i) => {
        if (i < 4) return null;
        const slice = bars.slice(i - 4, i + 1);
        return { time: bars[i].time as any, value: slice.reduce((s, b) => s + b.close, 0) / 5 };
      }).filter(Boolean) as any[];
      ma5.setData(ma5Data);
    }

    // MA20
    if (bars.length >= 20) {
      const ma20 = chart.addSeries(LineSeries, { color: "#8b5cf6", lineWidth: 1, priceLineVisible: false });
      const ma20Data = bars.map((_, i) => {
        if (i < 19) return null;
        const slice = bars.slice(i - 19, i + 1);
        return { time: bars[i].time as any, value: slice.reduce((s, b) => s + b.close, 0) / 20 };
      }).filter(Boolean) as any[];
      ma20.setData(ma20Data);
    }

    chart.timeScale().fitContent();

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [bars]);

  return <div ref={containerRef} className="w-full" />;
}
