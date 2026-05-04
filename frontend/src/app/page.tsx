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

  const statusText = status?.status === "running" ? "运行中" : status?.status === "paused" ? "已暂停" : "加载中...";

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">总览面板</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard title="系统状态" value={statusText} />
        <StatCard title="可用资金" value={`$${(status?.cash || 0).toLocaleString()}`} />
        <StatCard title="持仓数量" value={String(status?.positions || 0)} />
        <StatCard title="累计盈亏" value={`$${(stats?.total_pnl || 0).toLocaleString()}`} />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard title="总交易次数" value={String(stats?.total_trades || 0)} />
        <StatCard title="胜率" value={`${((stats?.win_rate || 0) * 100).toFixed(0)}%`} />
        <StatCard title="盈利次数" value={String(stats?.wins || 0)} />
        <StatCard title="亏损次数" value={String(stats?.losses || 0)} />
      </div>
    </div>
  );
}
