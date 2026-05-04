"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Watchlist() {
  const [symbols, setSymbols] = useState<any[]>([]);
  const [signals, setSignals] = useState<any[]>([]);

  useEffect(() => {
    api.getSymbols().then(setSymbols).catch(() => {});
    api.getSignals().then(setSignals).catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">股票池</h1>
      <table className="w-full bg-white rounded shadow">
        <thead>
          <tr className="border-b">
            <th className="p-3 text-left">股票代码</th>
            <th className="p-3 text-left">状态</th>
            <th className="p-3 text-left">最新信号</th>
          </tr>
        </thead>
        <tbody>
          {symbols.map((s) => {
            const sig = signals.find((sig) => sig.ticker === s.ticker);
            return (
              <tr key={s.ticker} className="border-b hover:bg-gray-50">
                <td className="p-3 font-mono font-bold">{s.ticker}</td>
                <td className="p-3">{s.is_active ? "活跃" : "暂停"}</td>
                <td className="p-3">{sig ? `${sig.type}: ${sig.reason || sig.strategy || ""}` : "—"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
