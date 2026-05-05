"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatCard } from "@/components/StatCard";

export default function Strategy() {
  const [stats, setStats] = useState<any>(null);
  const [breakoutStats, setBreakoutStats] = useState<any>(null);
  const [reversionStats, setReversionStats] = useState<any>(null);

  useEffect(() => {
    api.getTradeStats().then(setStats).catch(() => {});
    // Fetch per-strategy stats
    fetch("/api/trades/stats/breakout").then(r => r.json()).then(setBreakoutStats).catch(() => {});
    fetch("/api/trades/stats/mean_reversion").then(r => r.json()).then(setReversionStats).catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">策略管理</h1>
      <div className="grid grid-cols-2 gap-4 mb-6">
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="font-bold text-lg mb-2">趋势突破</h3>
          <p className="text-sm text-gray-500 mb-3">N根K线新高 + 放量</p>
          <div className="grid grid-cols-2 gap-2">
            <StatCard title="胜率" value={`${((breakoutStats?.win_rate || 0) * 100).toFixed(0)}%`} />
            <StatCard title="盈亏比" value={String(breakoutStats?.profit_factor || "-")} />
            <StatCard title="总盈亏" value={`$${(breakoutStats?.total_pnl || 0).toLocaleString()}`} />
            <StatCard title="最大回撤" value={`$${(breakoutStats?.max_drawdown || 0).toLocaleString()}`} />
          </div>
        </div>
        <div className="bg-white rounded-lg shadow p-4">
          <h3 className="font-bold text-lg mb-2">超跌反弹</h3>
          <p className="text-sm text-gray-500 mb-3">RSI &lt; 25 + VWAP偏离</p>
          <div className="grid grid-cols-2 gap-2">
            <StatCard title="胜率" value={`${((reversionStats?.win_rate || 0) * 100).toFixed(0)}%`} />
            <StatCard title="盈亏比" value={String(reversionStats?.profit_factor || "-")} />
            <StatCard title="总盈亏" value={`$${(reversionStats?.total_pnl || 0).toLocaleString()}`} />
            <StatCard title="最大回撤" value={`$${(reversionStats?.max_drawdown || 0).toLocaleString()}`} />
          </div>
        </div>
      </div>
      <h2 className="text-xl font-bold mt-6 mb-4">总体表现</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard title="胜率" value={`${((stats?.win_rate || 0) * 100).toFixed(0)}%`} />
        <StatCard title="累计盈亏" value={`$${(stats?.total_pnl || 0).toLocaleString()}`} />
        <StatCard title="总交易次数" value={String(stats?.total_trades || 0)} />
        <StatCard title="可用资金" value={`$${(stats?.cash || 0).toLocaleString()}`} />
      </div>
    </div>
  );
}
