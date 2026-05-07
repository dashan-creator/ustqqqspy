"use client";
import { useEffect, useState, useCallback } from "react";
import { PnlChart } from "@/components/PnlChart";
import { PositionsTable } from "@/components/PositionsTable";
import { api } from "@/lib/api";
import { useWebSocket } from "@/lib/useWebSocket";

export default function Dashboard() {
  const [status, setStatus] = useState<any>(null);
  const [stats, setStats] = useState<any>(null);
  const [trades, setTrades] = useState<any[]>([]);
  const [signals, setSignals] = useState<any[]>([]);
  const [positions, setPositions] = useState<any[]>([]);
  const { lastMessage, connected } = useWebSocket("ws://localhost:8001/ws/signals");

  const refresh = useCallback(() => {
    api.getSystemStatus().then(setStatus).catch(() => {});
    api.getTradeStats().then(setStats).catch(() => {});
    api.getTrades().then(setTrades).catch(() => {});
    api.getSignals().then(setSignals).catch(() => {});
    fetch("http://localhost:8001/api/system/positions").then((r) => r.json()).then(setPositions).catch(() => {});
  }, []);

  useEffect(() => { refresh(); }, [refresh]);
  useEffect(() => { if (lastMessage) refresh(); }, [lastMessage, refresh]);

  const statusText = status?.status === "running" ? "运行中" : status?.status === "paused" ? "已暂停" : "加载中...";
  const statusColor = status?.status === "running" ? "var(--green)" : "var(--red)";

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
        <span className="text-sm" style={{ color: connected ? "var(--green)" : "var(--text-muted)" }}>
          {connected ? "● 实时" : "○ 离线"}
        </span>
      </div>

      {/* 指标卡 */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="stat-card">
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>系统状态</p>
          <p className="text-2xl font-bold" style={{ color: statusColor }}>{statusText}</p>
        </div>
        <div className="stat-card">
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>可用资金</p>
          <p className="text-2xl font-bold">${(status?.cash || 0).toLocaleString()}</p>
        </div>
        <div className="stat-card">
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>持仓数量</p>
          <p className="text-2xl font-bold">{status?.positions || 0}</p>
        </div>
        <div className="stat-card">
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>累计盈亏</p>
          <p className={`text-2xl font-bold ${(stats?.total_pnl || 0) >= 0 ? "pnl-positive" : "pnl-negative"}`}>
            ${(stats?.total_pnl || 0).toLocaleString()}
          </p>
        </div>
      </div>

      {/* 持仓表格 */}
      {positions.length > 0 && (
        <div className="mb-6">
          <h2 className="text-lg font-bold mb-3">当前持仓</h2>
          <PositionsTable positions={positions} />
        </div>
      )}

      {/* 图表和交易 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="dark-card">
          <h2 className="text-lg font-bold mb-4">累计盈亏曲线</h2>
          <PnlChart data={pnlData} />
        </div>

        <div className="dark-card">
          <h2 className="text-lg font-bold mb-4">最近交易</h2>
          <div className="space-y-2 max-h-[300px] overflow-y-auto">
            {trades.slice(0, 10).map((t: any, i: number) => (
              <div key={i} className="flex justify-between items-center p-2 rounded" style={{ backgroundColor: "var(--bg-tertiary)" }}>
                <div>
                  <span className="font-mono font-bold">{t.ticker}</span>
                  <span className="ml-2 text-sm" style={{ color: "var(--text-muted)" }}>{t.strategy}</span>
                </div>
                <span className={`font-bold ${(t.pnl || 0) >= 0 ? "pnl-positive" : "pnl-negative"}`}>
                  {(t.pnl || 0) >= 0 ? "+" : ""}{(t.pnl || 0).toFixed(2)}
                </span>
              </div>
            ))}
            {trades.length === 0 && <p style={{ color: "var(--text-muted)" }} className="text-center py-4">暂无交易</p>}
          </div>
        </div>
      </div>

      {/* 最新信号 */}
      {signals.length > 0 && (
        <div className="mt-6 dark-card">
          <h2 className="text-lg font-bold mb-4">最新信号</h2>
          <div className="space-y-2">
            {signals.slice(0, 5).map((s: any, i: number) => (
              <div key={i} className="flex justify-between items-center p-2 rounded" style={{ backgroundColor: "rgba(59,130,246,0.1)" }}>
                <div>
                  <span className="font-mono font-bold">{s.ticker || s.type}</span>
                  <span className="ml-2 text-sm" style={{ color: "var(--text-secondary)" }}>{s.strategy || s.reason || ""}</span>
                </div>
                <span className="text-xs" style={{ color: "var(--text-muted)" }}>{s.timestamp ? new Date(s.timestamp).toLocaleTimeString("zh-CN") : ""}</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
