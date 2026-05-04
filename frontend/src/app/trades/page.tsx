"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";

export default function Trades() {
  const [trades, setTrades] = useState<any[]>([]);

  useEffect(() => { api.getTrades().then(setTrades).catch(() => {}); }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">交易日志</h1>
      <table className="w-full bg-white rounded shadow">
        <thead>
          <tr className="border-b">
            <th className="p-3 text-left">股票</th>
            <th className="p-3 text-left">策略</th>
            <th className="p-3 text-right">入场价</th>
            <th className="p-3 text-right">出场价</th>
            <th className="p-3 text-right">盈亏</th>
            <th className="p-3 text-left">原因</th>
          </tr>
        </thead>
        <tbody>
          {trades.length === 0 ? (
            <tr><td colSpan={6} className="p-6 text-center text-gray-400">暂无交易记录</td></tr>
          ) : trades.map((t, i) => (
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
