"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Watchlist() {
  const [symbols, setSymbols] = useState<any[]>([]);
  const [signals, setSignals] = useState<any[]>([]);
  const [quotes, setQuotes] = useState<Record<string, any>>({});

  useEffect(() => {
    api.getSymbols().then(setSymbols).catch(() => {});
    api.getSignals().then(setSignals).catch(() => {});
  }, []);

  useEffect(() => {
    if (symbols.length === 0) return;
    const fetchQuotes = () => {
      symbols.forEach((s) => {
        fetch(`http://localhost:8001/api/market/quote/${s.ticker}`)
          .then((r) => r.json())
          .then((q) => setQuotes((prev) => ({ ...prev, [s.ticker]: q })))
          .catch(() => {});
      });
    };
    fetchQuotes();
    const interval = setInterval(fetchQuotes, 30000);
    return () => clearInterval(interval);
  }, [symbols]);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">股票池</h1>
      <div className="bg-white rounded-lg shadow overflow-hidden">
        <table className="w-full">
          <thead className="bg-gray-50">
            <tr>
              <th className="p-3 text-left text-sm font-semibold text-gray-600">股票代码</th>
              <th className="p-3 text-right text-sm font-semibold text-gray-600">当前价格</th>
              <th className="p-3 text-right text-sm font-semibold text-gray-600">涨跌幅</th>
              <th className="p-3 text-left text-sm font-semibold text-gray-600">状态</th>
              <th className="p-3 text-left text-sm font-semibold text-gray-600">最新信号</th>
            </tr>
          </thead>
          <tbody>
            {symbols.map((s) => {
              const q = quotes[s.ticker];
              const sig = signals.find((sig) => sig.ticker === s.ticker);
              const changePct = q?.change_pct || 0;
              const changeColor = changePct > 0 ? "text-green-600" : changePct < 0 ? "text-red-600" : "text-gray-500";

              return (
                <tr key={s.ticker} className="border-b hover:bg-gray-50 transition-colors">
                  <td className="p-3">
                    <span className="font-mono font-bold text-lg">{s.ticker}</span>
                  </td>
                  <td className="p-3 text-right font-mono">
                    {q?.price ? `$${q.price.toFixed(2)}` : "—"}
                  </td>
                  <td className={`p-3 text-right font-mono font-bold ${changeColor}`}>
                    {q?.price ? `${changePct >= 0 ? "+" : ""}${changePct.toFixed(2)}%` : "—"}
                  </td>
                  <td className="p-3">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${s.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                      {s.is_active ? "活跃" : "暂停"}
                    </span>
                  </td>
                  <td className="p-3 text-sm text-gray-600">
                    {sig ? `${sig.type}: ${sig.reason || sig.strategy || ""}` : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
