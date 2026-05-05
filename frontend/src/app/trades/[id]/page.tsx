"use client";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { StatCard } from "@/components/StatCard";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export default function TradeDetail() {
  const params = useParams();
  const [trade, setTrade] = useState<any>(null);

  useEffect(() => {
    fetch(`${API_BASE}/api/trades`, { cache: "no-store" })
      .then((r) => r.json())
      .then((trades) => {
        const found = trades.find((t: any) => String(t.id) === String(params.id) || String(trades.indexOf(t)) === String(params.id));
        setTrade(found);
      })
      .catch(() => {});
  }, [params.id]);

  if (!trade) {
    return <div className="text-gray-400 text-center py-8">加载中...</div>;
  }

  const pnlColor = (trade.pnl || 0) >= 0 ? "text-green-600" : "text-red-600";

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">交易详情</h1>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard title="股票" value={trade.ticker || "-"} />
        <StatCard title="策略" value={trade.strategy || "-"} />
        <StatCard title="数量" value={String(trade.quantity || "-")} />
        <StatCard title="盈亏" value={`$${trade.pnl || 0}`} />
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <StatCard title="入场价" value={`$${trade.entry_price || "-"}`} />
        <StatCard title="出场价" value={`$${trade.exit_price || "-"}`} />
        <StatCard title="盈亏比例" value={`${trade.pnl_pct || 0}%`} />
        <StatCard title="时间" value={trade.timestamp ? new Date(trade.timestamp).toLocaleString("zh-CN") : "-"} />
      </div>
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <h2 className="text-lg font-bold mb-2">交易原因</h2>
        <p className="text-gray-700">{trade.reason || "无"}</p>
      </div>
      {trade.llm_review && (
        <div className="bg-blue-50 rounded-lg shadow p-4">
          <h2 className="text-lg font-bold mb-2">LLM 复盘</h2>
          <p className="text-gray-700 whitespace-pre-wrap">{trade.llm_review}</p>
        </div>
      )}
    </div>
  );
}
