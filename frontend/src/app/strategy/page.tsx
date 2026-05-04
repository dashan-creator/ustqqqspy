"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatCard } from "@/components/StatCard";

export default function Strategy() {
  const [stats, setStats] = useState<any>(null);

  useEffect(() => { api.getTradeStats().then(setStats).catch(() => {}); }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Strategy</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard title="Breakout" value="Active" subtitle="N-bar high + volume" />
        <StatCard title="Mean Reversion" value="Active" subtitle="RSI < 25 + VWAP deviation" />
      </div>
      <h2 className="text-xl font-bold mt-6 mb-4">Performance</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard title="Win Rate" value={`${((stats?.win_rate || 0) * 100).toFixed(0)}%`} />
        <StatCard title="Total PnL" value={`$${(stats?.total_pnl || 0).toLocaleString()}`} />
        <StatCard title="Total Trades" value={String(stats?.total_trades || 0)} />
        <StatCard title="Cash" value={`$${(stats?.cash || 0).toLocaleString()}`} />
      </div>
    </div>
  );
}
