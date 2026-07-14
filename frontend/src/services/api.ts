import axios from 'axios';
import type { BacktestResult, FactorEvalResult, FactorInfo, KlineData, SymbolInfo, TradeRecord } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 60000,
});

export const dataApi = {
  getSymbols: (market_type: string = 'spot') =>
    api.get<SymbolInfo[]>('/api/symbols', { params: { market_type } }).then((res) => res.data),

  getKlines: (params: {
    symbol: string;
    interval: string;
    market_type: string;
    from: string;
    to: string;
  }) => api.get<KlineData[]>('/api/data/klines', { params }).then((res) => res.data),
};

export const factorApi = {
  getBuiltins: () =>
    api.get<{ factors: FactorInfo[] }>('/api/factor/builtins').then((res) => res.data.factors),

  evalFactor: (data: {
    mode: 'formula' | 'python';
    expression?: string;
    code?: string;
    symbol: string;
    interval: string;
    market_type: string;
    from: string;
    to: string;
  }) => api.post<FactorEvalResult>('/api/factor/eval', data).then((res) => res.data),
};

export const backtestApi = {
  runBacktest: (data: { strategy: Record<string, any>; data: Record<string, any> }) =>
    api.post<BacktestResult>('/api/backtest/run', data).then((res) => res.data),

  getBacktest: (id: string) =>
    api.get<BacktestResult>(`/api/backtest/${id}`).then((res) => res.data),

  getEquity: (id: string) =>
    api.get<{ timestamp: string; equity: number }[]>(`/api/backtest/${id}/equity`).then((res) => res.data),

  getTrades: (id: string) =>
    api.get<TradeRecord[]>(`/api/backtest/${id}/trades`).then((res) => res.data),
};

export const strategyApi = {
  listStrategies: () =>
    api.get<{ strategies: any[] }>('/api/strategies').then((res) => res.data.strategies),

  createStrategy: (data: { name: string; description?: string; config: Record<string, any> }) =>
    api.post('/api/strategies', data).then((res) => res.data),
};
