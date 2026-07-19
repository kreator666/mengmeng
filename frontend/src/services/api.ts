import axios from 'axios';
import type { BacktestResult, CustomFactor, FactorEvalResult, FactorInfo, FibLevelsResult, KlineData, SupportLevelAnalyzeResult, SymbolInfo, TradeRecord } from '../types';

// 默认同源相对路径：生产由 FastAPI 托管前端与 API（单端口），开发走 vite proxy
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 180000,
});

export const dataApi = {
  getSymbols: (market_type: string = 'spot', provider: string = 'gateio') =>
    api.get<SymbolInfo[]>('/api/symbols', { params: { market_type, provider } }).then((res) => res.data),

  getKlines: (params: {
    symbol: string;
    interval: string;
    market_type: string;
    provider: string;
    from: string;
    to: string;
  }) => api.get<KlineData[]>('/api/data/klines', { params }).then((res) => res.data),
};

export const factorApi = {
  getBuiltins: () =>
    api.get<{ factors: FactorInfo[] }>('/api/factor/builtins').then((res) => res.data.factors),

  getFactorLibrary: () =>
    api.get<{ builtins: FactorInfo[]; custom: CustomFactor[] }>('/api/factor/library').then((res) => res.data),

  getCustomFactors: () =>
    api.get<{ factors: CustomFactor[] }>('/api/factors').then((res) => res.data.factors),

  getCustomFactor: (id: string) =>
    api.get<CustomFactor>(`/api/factors/${id}`).then((res) => res.data),

  createCustomFactor: (data: { name: string; category?: string; description?: string; mode: 'formula' | 'python'; code: string }) =>
    api.post<CustomFactor>('/api/factors', data).then((res) => res.data),

  updateCustomFactor: (id: string, data: Partial<Omit<CustomFactor, 'id' | 'created_at' | 'updated_at'>>) =>
    api.put<CustomFactor>(`/api/factors/${id}`, data).then((res) => res.data),

  deleteCustomFactor: (id: string) =>
    api.delete(`/api/factors/${id}`).then((res) => res.data),

  evalFactor: (data: {
    mode: 'formula' | 'python';
    expression?: string;
    code?: string;
    symbol: string;
    interval: string;
    market_type: string;
    provider: string;
    from: string;
    to: string;
  }) => api.post<FactorEvalResult>('/api/factor/eval', data).then((res) => res.data),
};

export const backtestApi = {
  runBacktest: (data: { strategy: Record<string, any>; data: Record<string, any> }) =>
    api.post<BacktestResult>('/api/backtest/run', data).then((res) => res.data),

  listBacktests: (limit?: number) =>
    api.get<{ results: BacktestResult[] }>('/api/backtest', { params: { limit } }).then((res) => res.data.results),

  getBacktest: (id: string) =>
    api.get<BacktestResult>(`/api/backtest/${id}`).then((res) => res.data),

  getEquity: (id: string) =>
    api.get<{ timestamp: string; equity: number }[]>(`/api/backtest/${id}/equity`).then((res) => res.data),

  getTrades: (id: string) =>
    api.get<TradeRecord[]>(`/api/backtest/${id}/trades`).then((res) => res.data),
};

export const supportLevelApi = {
  analyze: (params: {
    symbol: string;
    interval: string;
    market_type: string;
    provider: string;
    from: string;
    to: string;
    lookback?: number;
    min_range?: number;
    touch_tolerance?: number;
    break_tolerance?: number;
    bounce_bars?: number;
    bounce_threshold?: number;
  }) => api.get<SupportLevelAnalyzeResult>('/api/support-level/analyze', { params }).then((res) => res.data),
};

export const fibApi = {
  getFibLevels: (params: {
    symbol: string;
    interval: string;
    market_type: string;
    provider: string;
    from?: string;
    to?: string;
    breakout_factor?: number;
    fib_low?: number;
    fib_high?: number;
  }) => api.get<FibLevelsResult>('/api/fib-levels', { params }).then((res) => res.data),
};

export const strategyApi = {
  listStrategies: () =>
    api.get<{ strategies: any[] }>('/api/strategies').then((res) => res.data.strategies),

  createStrategy: (data: { name: string; description?: string; config: Record<string, any> }) =>
    api.post('/api/strategies', data).then((res) => res.data),
};
