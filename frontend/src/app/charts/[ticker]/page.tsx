"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { CandlestickChart } from "@/components/CandlestickChart";

export default function ChartPage() {
  const params = useParams();
  const ticker = params.ticker as string;
  const [bars, setBars] = useState<any[]>([]);
  const [interval, setInterval] = useState("15m");

  useEffect(() => {
    if (!ticker) return;
    fetch(`http://localhost:8001/api/market/bars/${ticker}?interval=${interval}&period=5d`)
      .then((r) => r.json())
      .then((data) => {
        if (Array.isArray(data)) {
          setBars(data.map((b: any) => ({
            time: b.Datetime || b.bar_time || b.time || "",
            open: b.open || b.Open || 0,
            high: b.high || b.High || 0,
            low: b.low || b.Low || 0,
            close: b.close || b.Close || 0,
            volume: b.volume || b.Volume || 0,
          })));
        }
      })
      .catch(() => {});
  }, [ticker, interval]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">{ticker} K线图</h1>
        <div className="flex gap-2">
          {["5m", "15m", "1h", "1D"].map((tf) => (
            <button
              key={tf}
              onClick={() => setInterval(tf)}
              className="px-3 py-1 rounded text-sm font-medium transition-colors"
              style={{
                backgroundColor: interval === tf ? "var(--accent)" : "var(--bg-tertiary)",
                color: interval === tf ? "white" : "var(--text-secondary)",
              }}
            >
              {tf}
            </button>
          ))}
        </div>
      </div>
      <div className="dark-card p-0 overflow-hidden">
        {bars.length > 0 ? (
          <CandlestickChart bars={bars} />
        ) : (
          <div className="text-center py-20" style={{ color: "var(--text-muted)" }}>
            加载中...
          </div>
        )}
      </div>
    </div>
  );
}
