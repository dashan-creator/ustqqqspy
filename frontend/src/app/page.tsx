"use client";
import { useEffect, useState } from "react";
import { StatCard } from "@/components/StatCard";
import { api } from "@/lib/api";

export default function Dashboard() {
  const [status, setStatus] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);

  useEffect(() => {
    api.getSystemStatus().then(setStatus).catch(() => {});
    api.getTradeStats().then(setStats).catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Dashboard</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard title="System" value={status?.status || "..."} />
        <StatCard title="Cash" value={`$${(status?.cash || 0).toLocaleString()}`} />
        <StatCard title="Positions" value={String(status?.positions || 0)} />
        <StatCard title="Total PnL" value={`$${(stats?.total_pnl || 0).toLocaleString()}`} />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard title="Total Trades" value={String(stats?.total_trades || 0)} />
        <StatCard title="Win Rate" value={`${((stats?.win_rate || 0) * 100).toFixed(0)}%`} />
        <StatCard title="Wins" value={String(stats?.wins || 0)} />
        <StatCard title="Losses" value={String(stats?.losses || 0)} />
      </div>
    </div>
  );
}
