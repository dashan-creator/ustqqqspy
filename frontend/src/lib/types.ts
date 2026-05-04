export interface Quote {
  ticker: string;
  price: number;
  change_pct: number;
  volume: number;
}

export interface Signal {
  type: string;
  ticker?: string;
  strategy?: string;
  direction?: string;
  entry_price?: number;
  stop_loss?: number;
  take_profit?: number;
  quantity?: number;
  reason?: string;
  timestamp?: string;
}

export interface Trade {
  ticker: string;
  entry_price: number;
  exit_price: number;
  pnl: number;
  pnl_pct: number;
  strategy: string;
  reason: string;
  timestamp: string;
}

export interface TradeStats {
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  total_pnl: number;
  cash: number;
}

export interface SystemStatus {
  status: string;
  positions: number;
  cash: number;
}
