"use client";
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";

interface PnlChartProps {
  data: { name: string; pnl: number }[];
  height?: number;
}

export function PnlChart({ data, height = 300 }: PnlChartProps) {
  if (!data || data.length === 0) {
    return <div className="text-gray-400 text-center py-8">暂无数据</div>;
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />
        <XAxis dataKey="name" />
        <YAxis />
        <Tooltip />
        <Line type="monotone" dataKey="pnl" stroke="#3b82f6" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}
