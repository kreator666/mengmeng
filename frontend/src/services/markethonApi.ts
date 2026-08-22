import axios from 'axios';

import type {
  MarkethonBacktestQuantileRequest,
  MarkethonBacktestQuantileResponse,
  MarkethonBatchDefineRequest,
  MarkethonBatchDefineResponse,
  MarkethonBuiltinMappingsResponse,
  MarkethonDefineFactorRequest,
  MarkethonDefineFactorResponse,
  MarkethonEvaluateAllRequest,
  MarkethonEvaluateJobRequest,
  MarkethonEvaluateJobResponse,
  MarkethonEvaluateJobStatus,
  MarkethonEvaluateRequest,
  MarkethonEvaluateResult,
  MarkethonFactorMapCreateRequest,
  MarkethonFactorMapListResponse,
  MarkethonFactorsResponse,
  MarkethonHealthResponse,
  MarkethonLoadDataRequest,
  MarkethonLoadDataResponse,
  MarkethonLoginRequest,
  MarkethonLoginResponse,
  MarkethonSelectStocksRequest,
  MarkethonSelectStocksResponse,
  MarkethonStatusResponse,
  MarkethonSubmitScoreRequest,
  MarkethonSubmitScoreResponse,
  MarkethonSymbolsResponse,
  MarkethonWalkForwardRequest,
  MarkethonWalkForwardResponse,
} from '../types/markethon';

// 与 services/api.ts 同一封装惯例：默认同源相对路径（生产由 FastAPI 托管，开发走 vite proxy）
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 180000,
});

export const markethonApi = {
  // 认证
  login: (data: MarkethonLoginRequest) =>
    api.post<MarkethonLoginResponse>('/api/markethon/auth/login', data).then((res) => res.data),

  // 系统
  getHealth: () =>
    api.get<MarkethonHealthResponse>('/api/markethon/health').then((res) => res.data),

  getStatus: () =>
    api.get<MarkethonStatusResponse>('/api/markethon/status').then((res) => res.data),

  // 数据
  listSymbols: (limit?: number) =>
    api.get<MarkethonSymbolsResponse>('/api/markethon/data/symbols', { params: { limit } }).then((res) => res.data),

  loadData: (data: MarkethonLoadDataRequest) =>
    api.post<MarkethonLoadDataResponse>('/api/markethon/data/load', data).then((res) => res.data),

  // 因子
  listFactors: () =>
    api.get<MarkethonFactorsResponse>('/api/markethon/factors').then((res) => res.data),

  defineFactor: (data: MarkethonDefineFactorRequest) =>
    api.post<MarkethonDefineFactorResponse>('/api/markethon/factors/define', data).then((res) => res.data),

  evaluateFactors: (data: MarkethonEvaluateRequest) =>
    api.post<MarkethonEvaluateResult>('/api/markethon/factors/evaluate', data).then((res) => res.data),

  evaluateAll: (data: MarkethonEvaluateAllRequest) =>
    api.post<MarkethonEvaluateResult>('/api/markethon/factors/evaluate_all', data).then((res) => res.data),

  createEvaluateJob: (data: MarkethonEvaluateJobRequest) =>
    api.post<MarkethonEvaluateJobResponse>('/api/markethon/jobs/evaluate', data).then((res) => res.data),

  getEvaluateJob: (jobId: string) =>
    api.get<MarkethonEvaluateJobStatus>(`/api/markethon/jobs/${jobId}`).then((res) => res.data),

  // 回测
  backtestQuantile: (data: MarkethonBacktestQuantileRequest) =>
    api.post<MarkethonBacktestQuantileResponse>('/api/markethon/backtest/quantile', data).then((res) => res.data),

  walkForward: (data: MarkethonWalkForwardRequest) =>
    api.post<MarkethonWalkForwardResponse>('/api/markethon/backtest/walk_forward', data).then((res) => res.data),

  // 选股
  selectStocks: (data: MarkethonSelectStocksRequest) =>
    api.post<MarkethonSelectStocksResponse>('/api/markethon/selection', data).then((res) => res.data),

  // 项目因子映射辅助
  getBuiltinMappings: () =>
    api.get<MarkethonBuiltinMappingsResponse>('/api/markethon/builtin_mappings').then((res) => res.data),

  listFactorMaps: () =>
    api.get<MarkethonFactorMapListResponse>('/api/markethon/factor_maps').then((res) => res.data.maps),

  saveFactorMap: (data: MarkethonFactorMapCreateRequest) =>
    api.post<{ map: MarkethonFactorMapListResponse['maps'][number] }>('/api/markethon/factor_maps', data).then((res) => res.data.map),

  deleteFactorMap: (id: string) =>
    api.delete<{ deleted: boolean }>(`/api/markethon/factor_maps/${id}`).then((res) => res.data),

  defineFactorsBatch: (data: MarkethonBatchDefineRequest) =>
    api.post<MarkethonBatchDefineResponse>('/api/markethon/factors/define_batch', data).then((res) => res.data),

  // 天梯正式提交
  submitScore: (data: MarkethonSubmitScoreRequest) =>
    api.post<MarkethonSubmitScoreResponse>('/api/markethon/scores/submit', data, { timeout: 7200000 }).then((res) => res.data),
};

export default markethonApi;
