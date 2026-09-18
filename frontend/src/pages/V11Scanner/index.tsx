import { useEffect, useState } from 'react';
import { Button, Card, Col, Empty, Input, Popover, Row, Statistic, Table, Tabs, Tag, message } from 'antd';
import {
  TrophyOutlined,
  RiseOutlined,
  FallOutlined,
  ThunderboltOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import { v11ScannerApi } from '../../api/v11Scanner';
import type { V11Candidate, V11ScanResult } from '../../api/v11Scanner';

const FACTOR_NAMES = [
  'ROC60', 'MA60', 'STD10', 'BETA60', 'CORR10', 'VMA60',
  'LOW0', 'GAP723', 'PANIC_BUY', 'VSUMN60', 'VSUMP60',
];

const DIRECTION_COLORS: Record<string, string> = {
  强烈做多: '#f5222d',
  偏多: '#fa8c16',
  中性: '#999',
  偏空: '#1890ff',
  强烈做空: '#722ed1',
};

const directionRender = (v: string) => <Tag color={DIRECTION_COLORS[v] || '#999'}>{v}</Tag>;

// 防御 SPA 兜底路由返回的 HTML/异常结构，避免渲染期白屏
const isValidResult = (data: any): data is V11ScanResult =>
  !!data && Array.isArray(data.ranking) && typeof data.total_pairs === 'number';

const scoreRender = (v: number) => (
  <span style={{ color: v >= 0 ? '#52c41a' : '#f5222d', fontWeight: 'bold' }}>
    {v >= 0 ? '+' : ''}{v.toFixed(2)}
  </span>
);

const baseColumns = [
  {
    title: '排名',
    dataIndex: 'rank',
    key: 'rank',
    width: 60,
  },
  {
    title: '合约',
    dataIndex: 'pair',
    key: 'pair',
    width: 140,
    fixed: 'left' as const,
    render: (v: string) => <strong>{v.replace('_USDT', '')}</strong>,
  },
  {
    title: '综合得分',
    dataIndex: 'score',
    key: 'score',
    width: 100,
    render: scoreRender,
    sorter: (a: V11Candidate, b: V11Candidate) => a.score - b.score,
    defaultSortOrder: 'descend' as const,
  },
  {
    title: '方向',
    dataIndex: 'direction',
    key: 'direction',
    width: 90,
    render: directionRender,
  },
  {
    title: '现价',
    dataIndex: 'price',
    key: 'price',
    width: 110,
    render: (v: number) => v.toPrecision(6),
  },
];

// 各因子 z-score 列（截面标准化，正负代表相对全市场的偏离方向）
const zColumns = FACTOR_NAMES.map((name) => ({
  title: name,
  dataIndex: ['z', name],
  key: `z_${name}`,
  width: 80,
  render: (v: number | undefined) => {
    if (v === undefined) return '-';
    const color = v >= 0 ? '#52c41a' : '#f5222d';
    return <span style={{ color, fontSize: 12 }}>{v >= 0 ? '+' : ''}{v.toFixed(2)}</span>;
  },
  sorter: (a: V11Candidate, b: V11Candidate) => (a.z?.[name] ?? 0) - (b.z?.[name] ?? 0),
}));

const allColumns = [...baseColumns, ...zColumns];

const FactorDetail = ({ record }: { record: V11Candidate }) => (
  <div style={{ fontSize: 12, lineHeight: 1.8 }}>
    {FACTOR_NAMES.map((name) => (
      <div key={name} style={{ display: 'flex', justifyContent: 'space-between', gap: 24 }}>
        <span>{name}</span>
        <span>
          值 {record.factors?.[name]?.toFixed(6) ?? '-'}　
          <span style={{ color: (record.z?.[name] ?? 0) >= 0 ? '#52c41a' : '#f5222d' }}>
            z {record.z?.[name] >= 0 ? '+' : ''}{record.z?.[name]?.toFixed(2)}
          </span>
        </span>
      </div>
    ))}
  </div>
);

export default function V11Scanner() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<V11ScanResult | null>(null);
  const [keyword, setKeyword] = useState('');

  useEffect(() => {
    loadLatest();
  }, []);

  const loadLatest = async () => {
    try {
      const data = await v11ScannerApi.getLatest();
      if (!isValidResult(data)) {
        setResult(null);
        return;
      }
      setResult(data);
    } catch {
      setResult(null);
    }
  };

  const handleScan = async () => {
    setLoading(true);
    try {
      const data = await v11ScannerApi.scan();
      if (!isValidResult(data)) {
        message.error('后端响应异常：请确认后端服务已重启并加载 v11-scanner 路由');
        return;
      }
      setResult(data);
      const top = data.ranking[0];
      message.success(
        `扫描完成：${data.total_pairs} 个合约，有效评分 ${data.scanned} 个` +
        (top ? `，最高分 ${top.pair.replace('_USDT', '')} (${top.score >= 0 ? '+' : ''}${top.score.toFixed(2)})` : '')
      );
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '扫描失败');
    } finally {
      setLoading(false);
    }
  };

  const r = result;
  const kw = keyword.trim().toLowerCase();
  const matchPair = (c: V11Candidate) => !kw || c.pair.toLowerCase().includes(kw);
  const filteredAll = (r?.ranking || []).filter(matchPair);
  const filteredLong = (r?.top_long || []).filter(matchPair);
  const filteredShort = (r?.top_short || []).filter(matchPair);

  const tableProps = {
    columns: allColumns,
    rowKey: 'pair',
    size: 'small' as const,
    scroll: { x: 1400 },
    pagination: { pageSize: 20, showTotal: (t: number) => `共 ${t} 个` },
  };

  return (
    <div style={{ padding: 24 }}>
      <h1>
        <TrophyOutlined style={{ color: '#faad14' }} /> V11 策略扫描器
      </h1>
      <p style={{ color: '#666' }}>
        Markethon 天梯历史最高分策略（standard_score <b>47.07</b>，v11_core 组合，11 因子 ICIR 加权）。
        对 Gate.io 永续合约（范围与底部趋势扫描器一致）计算 11 个因子最新值，
        截面 z-score 加权合成打分：得分越高越偏多，越低越偏空。
      </p>

      <Card style={{ marginBottom: 24 }}>
        <Row gutter={16} align="middle">
          <Col>
            <Button
              type="primary"
              icon={<ThunderboltOutlined />}
              loading={loading}
              onClick={handleScan}
              size="large"
            >
              立即扫描
            </Button>
          </Col>
          <Col>
            <Input
              allowClear
              prefix={<SearchOutlined />}
              placeholder="输入币种模糊筛选，如 BTC / SOL"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              style={{ width: 280 }}
              size="large"
            />
          </Col>
          {r && (
            <Col flex="auto" style={{ textAlign: 'right' }}>
              <span style={{ color: '#999', fontSize: 12 }}>
                上次扫描：{r.scan_time} ｜ 共 {r.total_pairs} 个合约，有效评分 {r.scanned} 个
                {kw && ` ｜ 筛选匹配 ${filteredAll.length} 个`}
              </span>
            </Col>
          )}
        </Row>
      </Card>

      {r ? (
        <>
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            <Col xs={12} sm={6}>
              <Card>
                <Statistic
                  title="做多候选（得分>0）"
                  value={r.ranking.filter(c => c.score > 0).length}
                  suffix={<RiseOutlined style={{ color: '#52c41a' }} />}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card>
                <Statistic
                  title="做空候选（得分<0）"
                  value={r.ranking.filter(c => c.score < 0).length}
                  suffix={<FallOutlined style={{ color: '#f5222d' }} />}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card>
                <Statistic
                  title="最高得分"
                  value={r.ranking[0]?.score ?? 0}
                  precision={2}
                  valueStyle={{ color: '#52c41a' }}
                  suffix={r.ranking[0] ? r.ranking[0].pair.replace('_USDT', '') : ''}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card>
                <Statistic
                  title="最低得分"
                  value={r.ranking[r.ranking.length - 1]?.score ?? 0}
                  precision={2}
                  valueStyle={{ color: '#f5222d' }}
                  suffix={r.ranking.length ? r.ranking[r.ranking.length - 1].pair.replace('_USDT', '') : ''}
                />
              </Card>
            </Col>
          </Row>

          <Tabs
            defaultActiveKey="all"
            items={[
              {
                key: 'all',
                label: `📊 全部排序 (${filteredAll.length})`,
                children: (
                  <Table
                    {...tableProps}
                    dataSource={filteredAll}
                    columns={allColumns.map(c =>
                      c.key?.startsWith('z_')
                        ? { ...c, title: <Popover content={`权重 ${r.weights[c.title as string]?.toFixed(4)}`}><span>{c.title}</span></Popover> }
                        : c
                    )}
                    expandable={{
                      expandedRowRender: (record: V11Candidate) => <FactorDetail record={record} />,
                    }}
                  />
                ),
              },
              {
                key: 'long',
                label: `📈 做多候选 TOP30 (${filteredLong.length})`,
                children: filteredLong.length > 0 ? (
                  <Table {...tableProps} dataSource={filteredLong} />
                ) : (
                  <Empty description={kw ? `没有匹配「${keyword.trim()}」的做多候选` : '本次扫描无做多候选'} />
                ),
              },
              {
                key: 'short',
                label: `📉 做空候选 TOP30 (${filteredShort.length})`,
                children: filteredShort.length > 0 ? (
                  <Table {...tableProps} dataSource={filteredShort} />
                ) : (
                  <Empty description={kw ? `没有匹配「${keyword.trim()}」的做空候选` : '本次扫描无做空候选'} />
                ),
              },
            ]}
          />
        </>
      ) : (
        <Card>
          <Empty description="尚无扫描数据，点击「立即扫描」开始">
            <Button type="primary" loading={loading} onClick={handleScan}>
              立即扫描
            </Button>
          </Empty>
        </Card>
      )}
    </div>
  );
}
