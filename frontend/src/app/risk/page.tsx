"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatCard } from "@/components/StatCard";

export default function Risk() {
  const [risk, setRisk] = useState<any>(null);

  useEffect(() => { api.getRiskStatus().then(setRisk).catch(() => {}); }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">风控中心</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard title="熔断机制" value={risk?.circuit_breaker_paused ? "已触发" : "正常"} />
        <StatCard title="当日盈亏" value={`$${(risk?.daily_pnl || 0).toLocaleString()}`} />
        <StatCard title="连续亏损" value={String(risk?.consecutive_losses || 0)} />
        <StatCard title="可用资金" value={`$${(risk?.cash || 0).toLocaleString()}`} />
      </div>
      {risk?.circuit_breaker_reason && (
        <div className="bg-red-50 border border-red-200 rounded p-4 text-red-700">
          <strong>暂停原因：</strong> {risk.circuit_breaker_reason}
        </div>
      )}
    </div>
  );
}
