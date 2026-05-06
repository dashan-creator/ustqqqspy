const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001";

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, { cache: "no-store" });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export const api = {
  getSymbols: () => fetchJson<{ ticker: string; is_active: boolean }[]>("/api/market/symbols"),
  getSignals: () => fetchJson<any[]>("/api/signals"),
  getTrades: () => fetchJson<any[]>("/api/trades"),
  getTradeStats: () => fetchJson<any>("/api/trades/stats"),
  getRiskStatus: () => fetchJson<any>("/api/risk/status"),
  getSystemStatus: () => fetchJson<any>("/api/system/status"),
  pause: () => fetch(`${API_BASE}/api/system/pause`, { method: "POST" }),
  resume: () => fetch(`${API_BASE}/api/system/resume`, { method: "POST" }),
};
