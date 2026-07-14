export interface KlineData {
  timestamp: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
}

export interface SymbolInfo {
  symbol: string;
  market_type: string;
  base: string;
  quote: string;
}

export interface BacktestSummary {
  total_return: number;
  annualized_return: number;
  max_drawdown: number;
  max_drawdown_duration: number;
  volatility: number;
  downside_volatility: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  calmar_ratio: number;
  total_trades: number;
  win_rate: number;
  profit_factor: number;
  avg_trade_return: number;
  alpha: number;
}

export interface TradeRecord {
  entry_time: string;
  exit_time: string;
  side: 'long' | 'short';
  entry_price: number;
  exit_price: number;
  pnl: number;
  return_pct: number;
}

export interface BacktestResult {
  id: string;
  symbol: string;
  interval: string;
  market_type: string;
  from_date: string;
  to_date: string;
  summary: BacktestSummary;
  equity_curve: { timestamp: string; equity: number }[];
  drawdown_series: { timestamp: string; drawdown: number }[];
  trades: TradeRecord[];
  created_at?: string;
  updated_at?: string;
}

export interface StrategyConfig {
  name: string;
  factor_mode: 'formula' | 'python';
  factor_expression?: string;
  factor_code?: string;
  position_mode: string;
  position_ratio: number;
  initial_capital: number;
  fee_rate: number;
  slippage: number;
  stop_loss: number;
  take_profit: number;
  max_holding_bars: number;
}

export interface FactorInfo {
  name: string;
  category: string;
  signature: string;
  description: string;
}

export interface CustomFactor {
  id: string;
  name: string;
  category: string;
  description: string;
  mode: 'formula' | 'python';
  code: string;
  created_at: string;
  updated_at: string;
}

export interface FactorEvalResult {
  signal: { timestamp: string; signal: number; position: number }[];
  ic: number;
  rolling_ic: { timestamp: string; ic: number | null }[];
}
