"use client";
import { useEffect, useState, useCallback } from "react";
import { StatCard } from "@/components/StatCard";
import { PnlChart } from "@/components/PnlChart";
import { api } from "@/lib/api";
import { useWebSocket } from "@/lib/useWebSocket";

export default function Dashboard() {
  const [status, setStatus] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [trades, setTrades] = useState<any[]>([]);
  const [signals, setSignals] = useState<any[]>([]);
  const { lastMessage, connected } = useWebSocket("ws://localhost:8001/ws/signals");

  const refresh = useCallback(() => {
    api.getSystemStatus().then(setStatus).catch(() => {});
    api.getTradeStats().then(setStats).catch(() => {});
    api.getTrades().then(setTrades).catch(() => {});
    api.getSignals().then(setSignals).catch(() => {});
  }, []);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { if (lastMessage) refresh(); }, [lastMessage, refresh]);

  const statusText = status?.status === "running" ? "运行中" : status?.status === "paused" ? "已暂停" : "加载中...";
  const statusColor = status?.status === "running" ? "text-green-600" : "text-red-600";

  const pnlData = trades
    .filter((t: any) => t.pnl !== undefined)
    .reverse()
    .reduce((acc: { name: string; pnl: number }[], t: any, i: number) => {
      const prev = acc.length > 0 ? acc[acc.length - 1].pnl : 0;
      acc.push({ name: `#${i + 1}`, pnl: prev + t.pnl });
      return acc;
    }, []);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">总览面板</h1>
        <span className={`text-sm ${connected ? "text-green-500" : "text-gray-400"}`}>
          {connected ? "● 实时连接" : "○ 离线"}
        </span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard title="系统状态" value={statusText} />
        <StatCard title="可用资金" value={`$${(status?.cash || 0).toLocaleString()}`} />
        <StatCard title="持仓数量" value={String(status?.positions || 0)} />
        <StatCard title="累计盈亏" value={`$${(stats?.total_pnl || 0).toLocaleString()}`} />
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard title="总交易次数" value={String(stats?.total_trades || 0)} />
        <StatCard title="胜率" value={`${((stats?.win_rate || 0) * 100).toFixed(0)}%`} />
        <StatCard title="盈利次数" value={String(stats?.wins || 0)} />
        <StatCard title="亏损次数" value={String(stats?.losses || 0)} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-4">
          <h2 className="text-lg font-bold mb-4">累计盈亏曲线</h2>
          <PnlChart data={pnlData} />
        </div>

        <div className="bg-white rounded-lg shadow p-4">
          <h2 className="text-lg font-bold mb-4">最近交易</h2>
          <div className="space-y-2 max-h-[300px] overflow-y-auto">
            {trades.slice(0, 10).map((t: any, i: number) => (
              <div key={i} className="flex justify-between items-center p-2 bg-gray-50 rounded">
                <div>
                  <span className="font-mono font-bold">{t.ticker}</span>
                  <span className="ml-2 text-sm text-gray-500">{t.strategy}</span>
                </div>
                <span className={`font-bold ${t.pnl >= 0 ? "text-green-600" : "text-red-600"}`}>
                  {t.pnl >= 0 ? "+" : ""}{t.pnl?.toFixed(2)}
                </span>
              </div>
            ))}
            {trades.length === 0 && <p className="text-gray-400 text-center py-4">暂无交易</p>}
          </div>
        </div>
      </div>

      {signals.length > 0 && (
        <div className="mt-6 bg-white rounded-lg shadow p-4">
          <h2 className="text-lg font-bold mb-4">最新信号</h2>
          <div className="space-y-2">
            {signals.slice(0, 5).map((s: any, i: number) => (
              <div key={i} className="flex justify-between items-center p-2 bg-blue-50 rounded">
                <div>
                  <span className="font-mono font-bold">{s.ticker || s.type}</span>
                  <span className="ml-2 text-sm text-gray-600">{s.strategy || s.reason || ""}</span>
                </div>
                <span className="text-xs text-gray-400">{s.timestamp ? new Date(s.timestamp).toLocaleTimeString("zh-CN") : ""}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
