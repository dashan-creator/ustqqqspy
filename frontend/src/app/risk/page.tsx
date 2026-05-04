"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { StatCard } from "@/components/StatCard";

export default function Risk() {
  const [risk, setRisk] = useState<any>(null);

  useEffect(() => { api.getRiskStatus().then(setRisk).catch(() => {}); }, []);

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Risk Center</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard title="Circuit Breaker" value={risk?.circuit_breaker_paused ? "ON" : "OFF"} />
        <StatCard title="Daily PnL" value={`$${(risk?.daily_pnl || 0).toLocaleString()}`} />
        <StatCard title="Consecutive Losses" value={String(risk?.consecutive_losses || 0)} />
        <StatCard title="Cash" value={`$${(risk?.cash || 0).toLocaleString()}`} />
      </div>
      {risk?.circuit_breaker_reason && (
        <div className="bg-red-50 border border-red-200 rounded p-4 text-red-700">
          <strong>Pause Reason:</strong> {risk.circuit_breaker_reason}
        </div>
      )}
    </div>
  );
}
