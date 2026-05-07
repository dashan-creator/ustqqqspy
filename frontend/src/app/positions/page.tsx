"use client";
import { useEffect, useState } from "react";
import { PositionsTable } from "@/components/PositionsTable";
import { api } from "@/lib/api";

export default function Positions() {
  const [positions, setPositions] = useState<any[]>([]);
  const [status, setStatus] = useState<any>(null);

  useEffect(() => {
    fetch("http://localhost:8001/api/system/positions")
      .then((r) => r.json())
      .then(setPositions)
      .catch(() => {});
    api.getSystemStatus().then(setStatus).catch(() => {});
  }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">持仓管理</h1>
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="stat-card">
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>持仓数量</p>
          <p className="text-2xl font-bold">{positions.length}</p>
        </div>
        <div className="stat-card">
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>可用资金</p>
          <p className="text-2xl font-bold">${(status?.cash || 0).toLocaleString()}</p>
        </div>
        <div className="stat-card">
          <p className="text-sm" style={{ color: "var(--text-secondary)" }}>系统状态</p>
          <p className="text-2xl font-bold" style={{ color: status?.status === "running" ? "var(--green)" : "var(--red)" }}>
            {status?.status === "running" ? "运行中" : "已暂停"}
          </p>
        </div>
      </div>
      <PositionsTable positions={positions} />
    </div>
  );
}
