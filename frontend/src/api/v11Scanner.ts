import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 600000, // 扫描可能耗时数分钟
});

export interface V11Candidate {
  pair: string;
  price: number;
  score: number;
  rank: number;
  direction: string;
  factors: Record<string, number>;
  z: Record<string, number>;
}

export interface V11ScanResult {
  scan_time: string;
  exchange: string;
  strategy: string;
  leaderboard_score: number;
  total_pairs: number;
  scanned: number;
  weights: Record<string, number>;
  factor_stats: Record<string, { mean: number; std: number }>;
  ranking: V11Candidate[];
  top_long: V11Candidate[];
  top_short: V11Candidate[];
  min_bars: number;
}

export interface V11HistoryRecord {
  filename: string;
  scan_time: string;
  total_pairs: number;
  scanned: number;
  top_score: number | null;
}

export const v11ScannerApi = {
  scan: () =>
    api.post<V11ScanResult>('/api/v11-scanner/scan').then((res) => res.data),

  getLatest: () =>
    api.get<V11ScanResult>('/api/v11-scanner/latest').then((res) => res.data),

  getHistory: (limit: number = 20) =>
    api.get<{ records: V11HistoryRecord[] }>('/api/v11-scanner/history', { params: { limit } }).then((res) => res.data.records),
};
