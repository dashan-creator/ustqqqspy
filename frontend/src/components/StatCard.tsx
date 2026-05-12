export function StatCard({ title, value, subtitle }: { title: string; value: string; subtitle?: string }) {
  return (
    <div className="stat-card">
      <p className="text-sm text-gray-400">{title}</p>
      <p className="text-2xl font-bold">{value}</p>
      {subtitle && <p className="text-sm text-gray-500">{subtitle}</p>}
    </div>
  );
}
