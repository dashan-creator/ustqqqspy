"use client";

interface Position {
  ticker: string;
  quantity: number;
  avg_price: number;
  strategy: string;
  stop_loss: number;
  take_profit: number;
  current_price?: number;
}

export function PositionsTable({ positions }: { positions: Position[] }) {
  if (!positions || positions.length === 0) {
    return (
      <div className="dark-card text-center" style={{ color: "var(--text-muted)" }}>
        暂无持仓
      </div>
    );
  }

  return (
    <div className="dark-card overflow-hidden p-0">
      <table className="dark-table">
        <thead>
          <tr>
            <th>股票</th>
            <th>数量</th>
            <th>入场价</th>
            <th>当前价</th>
            <th>未实现盈亏</th>
            <th>止损</th>
            <th>止盈</th>
            <th>策略</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          {positions.map((p) => {
            const current = p.current_price || p.avg_price;
            const pnl = (current - p.avg_price) * p.quantity;
            const pnlPct = ((current - p.avg_price) / p.avg_price * 100);
            const pnlClass = pnl >= 0 ? "pnl-positive" : "pnl-negative";

            return (
              <tr key={p.ticker}>
                <td>
                  <a href={`/charts/${p.ticker}`} className="font-mono font-bold hover:underline" style={{ color: "var(--accent)" }}>
                    {p.ticker}
                  </a>
                </td>
                <td>{p.quantity}</td>
                <td className="font-mono">${p.avg_price.toFixed(2)}</td>
                <td className="font-mono">${current.toFixed(2)}</td>
                <td className={`font-mono font-bold ${pnlClass}`}>
                  {pnl >= 0 ? "+" : ""}{pnl.toFixed(2)} ({pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%)
                </td>
                <td className="font-mono" style={{ color: "var(--red)" }}>${p.stop_loss?.toFixed(2) || "—"}</td>
                <td className="font-mono" style={{ color: "var(--green)" }}>${p.take_profit?.toFixed(2) || "—"}</td>
                <td><span className="badge badge-blue">{p.strategy}</span></td>
                <td>
                  <button
                    className="btn-danger text-xs"
                    onClick={() => {
                      fetch(`http://localhost:8001/api/system/positions`, { method: "DELETE" })
                        .then(() => window.location.reload());
                    }}
                  >
                    平仓
                  </button>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
