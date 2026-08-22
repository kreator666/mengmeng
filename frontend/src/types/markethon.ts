/**
 * Markethon 比赛系统 API 类型定义。
 * 对应 design/game.md 中 https://markethon.fit:19371 的接口。
 */

// 认证
export interface MarkethonLoginRequest {
  username: string;
  password: string;
}

export interface MarkethonLoginResponse {
  access_token: string;
  token_type?: string;
}

// 系统
export interface MarkethonHealthResponse {
  ok: boolean;
}

export interface MarkethonStatusResponse {
  loaded: boolean;
  symbols?: number;
  date_range?: [string, string];
  custom_factors?: string[];
  trading_days?: number;
  alpha158_factors?: number;
  alpha360_factors?: number;
}

// 数据
export interface MarkethonSymbolsResponse {
  total: number;
  sample: string[];
}

export interface MarkethonLoadDataRequest {
  limit?: number;
  symbols?: string[];
  universe?: string | string[];
  start?: string;
  end?: string;
  alpha360?: boolean;
}

export interface MarkethonLoadDataResponse {
  loaded: boolean;
  symbols: number;
  trading_days: number;
  date_range: [string, string];
  alpha158_factors: number;
  alpha360_factors?: number;
}

// 因子
export interface MarkethonFactorsResponse {
  alpha158?: string[];
  alpha360?: string[];
  custom?: Record<string, string>;
}

export interface MarkethonDefineFactorRequest {
  name: string;
  expression: string;
}

export interface MarkethonDefineFactorResponse {
  registered: string;
  expression: string;
}

export interface MarkethonEvaluateRequest {
  names: string[];
  periods?: number[];
  quantiles?: number;
  top_n?: number;
}

export interface MarkethonEvaluateResult {
  count: number;
  factors: MarkethonFactorMetric[];
}

export interface MarkethonFactorMetric {
  factor: string;
  'IC均值': number;
  ICIR: number;
  't统计量': number;
  'IC>0占比': number;
  '多空收益': number;
}

export interface MarkethonEvaluateAllRequest {
  factor_set?: 'alpha158' | 'alpha360' | 'all';
  periods?: number[];
  quantiles?: number;
  top_n?: number;
}

export interface MarkethonEvaluateJobRequest {
  names?: string[] | null;
  factor_set?: 'alpha158' | 'alpha360' | 'all';
  periods?: number[];
  quantiles?: number;
}

export interface MarkethonEvaluateJobResponse {
  job_id: string;
}

export interface MarkethonEvaluateJobStatus {
  status: 'running' | 'done' | 'error';
  done?: number;
  total?: number;
  current?: string;
  elapsed_s?: number;
  eta_s?: number | null;
  result?: MarkethonEvaluateResult;
}

// 回测
export interface MarkethonBacktestQuantileRequest {
  names: string[];
  weights?: Record<string, number>;
  long_short?: boolean;
  periods?: number;
  quantiles?: number;
  benchmark?: string;
}

export interface MarkethonBacktestQuantileResponse {
  metrics: Record<string, string | number>;
  nav: Record<string, number | null>;
  series: Record<string, Record<string, number | null>>;
}

export interface MarkethonWalkForwardWindow {
  window: number;
  train_start: string;
  train_end: string;
  test_start: string;
  test_end: string;
  selected_factors: string[];
  selection_method: string;
  weights: Record<string, number>;
  top_icir: Record<string, number>;
}

export interface MarkethonWalkForwardRequest {
  names: string[];
  train_months?: number;
  test_months?: number;
  step_months?: number;
  long_short?: boolean;
  quantiles?: number;
  rebalance_periods?: number;
  category_counts?: Record<string, number>;
  uncategorized_count?: number;
  selection_method?: 'legacy' | 'robust';
  min_abs_icir?: number;
  min_abs_ic?: number;
  corr_threshold?: number;
  weight_shrinkage?: number;
  benchmark?: string;
  submit_score?: boolean;
}

export interface MarkethonWalkForwardScore {
  score: number;
  eligible: boolean;
  leaderboard_eligible: boolean;
  reason?: string;
  coverage_ratio?: number;
  valid_trading_days?: number;
  stock_count?: number;
  factor_count?: number;
  windows_count?: number;
  coverage?: {
    fixed_start: string;
    fixed_end: string;
    calendar_days: number;
    valid_days: number;
    leading_gap_days: number;
    max_gap_days: number;
    first_observed: string;
    last_observed: string;
  };
  score_components?: Record<string, number>;
  [key: string]: any;
}

export interface MarkethonWalkForwardResponse {
  metrics: Record<string, string | number>;
  nav: Record<string, number | null>;
  windows: MarkethonWalkForwardWindow[];
  standard_score?: MarkethonWalkForwardScore;
  submission?: Record<string, any>;
  submission_skipped?: boolean;
}

export interface MarkethonSubmitScoreRequest {
  names: string[];
  submission_key: string;
  train_months?: number;
  test_months?: number;
  step_months?: number;
  long_short?: boolean;
  quantiles?: number;
  rebalance_periods?: number;
  benchmark?: string;
  long_exposure?: number;
  short_exposure?: number;
  futures_cost?: number;
  selection_method?: string;
  min_abs_icir?: number;
  min_abs_ic?: number;
  corr_threshold?: number;
  weight_shrinkage?: number;
  category_counts?: Record<string, number> | null;
  uncategorized_count?: number | null;
  submit_score?: boolean;
}

export type MarkethonSubmitScoreResponse = MarkethonWalkForwardResponse;

// 选股
export interface MarkethonSelectStocksRequest {
  names: string[];
  weights?: Record<string, number>;
  top_n?: number;
  date?: string | null;
  min_amount_cny?: number;
  min_listed_days?: number;
}

export interface MarkethonStockScore {
  symbol: string;
  score: number;
  close: number;
  amount_cny: number;
  listed_days: number;
}

export interface MarkethonSelectStocksResponse {
  date: string;
  filters: {
    min_amount_cny: number;
    min_listed_days: number;
    before_filter: number;
    eligible: number;
  };
  long_top: MarkethonStockScore[];
  short_bottom: MarkethonStockScore[];
}

// 项目因子 → Markethon qlib 映射
export interface MarkethonBuiltinMapping {
  name: string;
  category: string;
  signature: string;
  description: string;
  supported: boolean;
  template?: string;
  example?: string;
  note?: string;
}

export interface MarkethonBuiltinMappingsResponse {
  mappings: Record<string, MarkethonBuiltinMapping>;
}

export interface MarkethonFactorMapItem {
  id: string;
  project_factor_id: string;
  project_factor_name: string;
  project_factor_mode: string;
  qlib_expression: string;
  markethon_name: string;
  created_at: string;
  updated_at: string;
}

export interface MarkethonFactorMapListResponse {
  maps: MarkethonFactorMapItem[];
}

export interface MarkethonFactorMapCreateRequest {
  project_factor_id: string;
  project_factor_name: string;
  project_factor_mode: string;
  qlib_expression: string;
  markethon_name: string;
}

export interface MarkethonDefineFactorItem {
  name: string;
  expression: string;
}

export interface MarkethonBatchDefineRequest {
  factors: MarkethonDefineFactorItem[];
  save_maps?: boolean;
}

export interface MarkethonBatchDefineResultItem {
  name: string;
  ok: boolean;
  data?: MarkethonDefineFactorResponse;
  error?: string;
  status?: number;
}

export interface MarkethonBatchDefineResponse {
  successes: number;
  failures: number;
  results: MarkethonBatchDefineResultItem[];
}
