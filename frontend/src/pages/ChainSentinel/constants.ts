import type { SentinelIndicator, SentinelLight, SentinelRegime } from '../../api/chainSentinel';

export const LIGHT_MAP: Record<SentinelLight, { color: string; bg: string; border: string; text: string }> = {
  green: { color: '#52c41a', bg: '#f6ffed', border: '#b7eb8f', text: '正常' },
  yellow: { color: '#faad14', bg: '#fffbe6', border: '#ffe58f', text: '警惕' },
  red: { color: '#ff4d4f', bg: '#fff2f0', border: '#ffccc7', text: '逃顶信号' },
};

export const REGIME_MAP: Record<SentinelRegime, { text: string; color: string }> = {
  A: { text: 'A · 良性循环', color: 'green' },
  B: { text: 'B · 高位消化', color: 'gold' },
  C: { text: 'C · 循环破裂', color: 'red' },
};

export const INDICATORS: { code: SentinelIndicator; label: string }[] = [
  { code: 'capex_growth', label: '巨头 Capex 环比增速' },
  { code: 'openai_next_round', label: 'OpenAI 下轮融资倍数' },
  { code: 'first_slowdown', label: '首个宣布减速的巨头' },
  { code: 'backlog_concentration', label: 'Backlog 欠款方集中度' },
];
