import axios from 'axios';

// 与 services/api.ts 同一封装惯例：默认同源相对路径（生产由 FastAPI 托管，开发走 vite proxy）。
// 扫描接口耗时数十秒，沿用 180s 超时。
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 180000,
});

/** 灯色三档：green 正常 / yellow 警惕 / red 逃顶信号 */
export type SentinelLight = 'green' | 'yellow' | 'red';

/** 情景判级：A 良性循环 / B 高位消化 / C 循环破裂 */
export type SentinelRegime = 'A' | 'B' | 'C';

/** 指标代码（固定四个） */
export type SentinelIndicator = 'capex_growth' | 'openai_next_round' | 'first_slowdown' | 'backlog_concentration';

export interface SentinelReasons {
  price: string[];
  news: string[];
  dashboard: string[];
  light: string[];
  news_error: string | null;
}

export interface SentinelStatusReady {
  ready: true;
  date: string;
  regime: SentinelRegime;
  price_score: number;
  news_score: number;
  dash_score: number;
  total_score: number;
  light: SentinelLight;
  reasons: SentinelReasons;
  created_at: string;
  dashboard_status: Record<string, SentinelLight>;
}

export interface SentinelStatusNotReady {
  ready: false;
  message: string;
}

export type SentinelStatus = SentinelStatusReady | SentinelStatusNotReady;

export interface SentinelMember {
  symbol: string;
  role: string;
  risk_score: number;
  reasons: string[];
}

/** POST /scan 响应 = status 全部字段 + 以下扩展字段 */
export interface SentinelScanResult extends SentinelStatusReady {
  prev_light: SentinelLight | null;
  members: SentinelMember[];
  news_hits: number;
  notified: boolean;
}

export interface SentinelHistoryItem {
  date: string;
  regime: SentinelRegime;
  price_score: number;
  news_score: number;
  dash_score: number;
  total_score: number;
  light: SentinelLight;
  reasons: SentinelReasons;
  created_at: string;
}

export interface SentinelNewsItem {
  news_id: string;
  date: string;
  title: string;
  url: string;
  source: string;
  tickers: string[];
  matched_keywords: string[];
  heavy: boolean;
  published_at: string;
}

export interface SentinelDashboardEntry {
  id: number;
  quarter: string;
  indicator: string;
  status: SentinelLight;
  value_text: string;
  note: string;
  updated_at: string;
}

export interface SentinelDashboard {
  indicators: string[];
  entries: SentinelDashboardEntry[];
  current_status: Record<string, SentinelLight>;
}

export interface SentinelEvent {
  id: number;
  ts: string;
  from_light: SentinelLight | null;
  to_light: SentinelLight;
  total_score: number;
  notified: boolean;
  detail: Record<string, any>;
}

export const chainSentinelApi = {
  getStatus: () =>
    api.get<SentinelStatus>('/api/chain-sentinel/status').then((res) => res.data),

  scan: () =>
    api.post<SentinelScanResult>('/api/chain-sentinel/scan').then((res) => res.data),

  getHistory: (days: number = 90) =>
    api
      .get<{ history: SentinelHistoryItem[] }>('/api/chain-sentinel/history', { params: { days } })
      .then((res) => res.data.history),

  getNews: (days: number = 7) =>
    api
      .get<{ news: SentinelNewsItem[] }>('/api/chain-sentinel/news', { params: { days } })
      .then((res) => res.data.news),

  getDashboard: () =>
    api.get<SentinelDashboard>('/api/chain-sentinel/dashboard').then((res) => res.data),

  saveDashboardEntry: (data: {
    quarter: string;
    indicator: string;
    status: SentinelLight;
    value_text: string;
    note: string;
  }) =>
    api
      .post<{ ok: boolean; current_status: Record<string, SentinelLight> }>('/api/chain-sentinel/dashboard', data)
      .then((res) => res.data),

  getEvents: (limit: number = 50) =>
    api
      .get<{ events: SentinelEvent[] }>('/api/chain-sentinel/events', { params: { limit } })
      .then((res) => res.data.events),
};
