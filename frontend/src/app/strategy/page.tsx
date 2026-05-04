"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatCard } from "@/components/StatCard";

export default function Strategy() {
  const [stats, setStats] = useState<any>(null);

  useEffect(() => { api.getTradeStats().then(setStats).catch(() => {}); }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">策略管理</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard title="趋势突破" value="运行中" subtitle="N根K线新高 + 放量" />
        <StatCard title="超跌反弹" value="运行中" subtitle="RSI < 25 + VWAP偏离" />
      </div>
      <h2 className="text-xl font-bold mt-6 mb-4">策略表现</h2>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard title="胜率" value={`${((stats?.win_rate || 0) * 100).toFixed(0)}%`} />
        <StatCard title="累计盈亏" value={`$${(stats?.total_pnl || 0).toLocaleString()}`} />
        <StatCard title="总交易次数" value={String(stats?.total_trades || 0)} />
        <StatCard title="可用资金" value={`$${(stats?.cash || 0).toLocaleString()}`} />
      </div>
    </div>
  );
}
