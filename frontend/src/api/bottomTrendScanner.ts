import axios from 'axios';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 600000, // 扫描可能耗时数分钟
});

export interface ScannerCandidate {
  pair: string;
  adx: number;
  cv: number;
  vr: number;
  gain5: number;
  gain20: number;
  ath_drop: number;
  atl_gain: number;
  bull_align: boolean;
  bull_partial: boolean;
  score: number;
  grade: string;
  zone: string;
  ar: number | null;
  status: string;
  ath: number;
  atl: number;
  ath_time: string;
  atl_time: string;
  cur: number;
  ts: string;
}

export interface ScannerResult {
  scan_time: string;
  exchange: string;
  total_pairs: number;
  all_candidates: ScannerCandidate[];
  trend_candidates: ScannerCandidate[];
  bottom_candidates: ScannerCandidate[];
  grades: Record<string, number>;
  zones: Record<string, number>;
  top_by_zone: Record<string, ScannerCandidate[]>;
  params: Record<string, number>;
}

export interface ScannerHistoryRecord {
  filename: string;
  scan_time: string;
  exchange: string;
  total_pairs: number;
  trend_count: number;
  bottom_count: number;
}

export const bottomTrendScannerApi = {
  scan: (exchange: string = 'gate') =>
    api.post<ScannerResult>('/api/bottom-trend-scanner/scan', { exchange }).then((res) => res.data),

  getLatest: (exchange: string = 'gate') =>
    api.get<ScannerResult>('/api/bottom-trend-scanner/latest', { params: { exchange } }).then((res) => res.data),

  getHistory: (exchange: string = 'gate', limit: number = 20) =>
    api.get<{ records: ScannerHistoryRecord[] }>('/api/bottom-trend-scanner/history', { params: { exchange, limit } }).then((res) => res.data.records),
};
