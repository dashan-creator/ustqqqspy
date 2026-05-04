"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Trades() {
  const [trades, setTrades] = useState<any[]>([]);

  useEffect(() => { api.getTrades().then(setTrades).catch(() => {}); }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Trade Log</h1>
      <table className="w-full bg-white rounded shadow">
        <thead>
          <tr className="border-b">
            <th className="p-3 text-left">Ticker</th>
            <th className="p-3 text-left">Strategy</th>
            <th className="p-3 text-right">Entry</th>
            <th className="p-3 text-right">Exit</th>
            <th className="p-3 text-right">PnL</th>
            <th className="p-3 text-left">Reason</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t, i) => (
            <tr key={i} className="border-b hover:bg-gray-50">
              <td className="p-3 font-mono font-bold">{t.ticker}</td>
              <td className="p-3">{t.strategy}</td>
              <td className="p-3 text-right">${t.entry_price}</td>
              <td className="p-3 text-right">${t.exit_price}</td>
              <td className={`p-3 text-right font-bold ${t.pnl >= 0 ? "text-green-600" : "text-red-600"}`}>
                ${t.pnl} ({t.pnl_pct}%)
              </td>
              <td className="p-3 text-sm text-gray-500">{t.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
