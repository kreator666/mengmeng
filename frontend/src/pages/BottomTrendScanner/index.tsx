import { useEffect, useState } from 'react';
import { Button, Card, Col, Empty, Row, Select, Statistic, Table, Tabs, Tag, message } from 'antd';
import {
  ThunderboltOutlined,
  RiseOutlined,
  FallOutlined,
  DotChartOutlined,
} from '@ant-design/icons';
import { bottomTrendScannerApi } from '../../api/bottomTrendScanner';
import type { ScannerCandidate, ScannerResult } from '../../api/bottomTrendScanner';

const EXCHANGES = [
  { value: 'gate', label: 'Gate.io 永续合约（~900个，最快）' },
  { value: 'binance', label: 'Binance 现货（~490个）' },
  { value: 'okx', label: 'OKX 现货（~350个）' },
];

const GRADE_COLORS: Record<string, string> = {
  AAA: '#f5222d',
  AA: '#fa8c16',
  A: '#faad14',
  B: '#52c41a',
  C: '#1890ff',
  D: '#999',
};

const ZONE_LABELS: Record<string, string> = {
  A: '浅回调 10-30%',
  B: '中回调 30-50%',
  C: '深回调 50-70%',
  D: '超跌反弹 70-85%',
};

const trendColumns = [
  {
    title: '合约',
    dataIndex: 'pair',
    key: 'pair',
    width: 160,
    fixed: 'left' as const,
    render: (v: string) => <strong>{v.replace('_USDT', '').replace('-USDT', '').replace('USDT', '')}</strong>,
  },
  {
    title: '等级',
    dataIndex: 'grade',
    key: 'grade',
    width: 70,
    render: (v: string) => <Tag color={GRADE_COLORS[v]}>{v}</Tag>,
  },
  {
    title: '得分',
    dataIndex: 'score',
    key: 'score',
    width: 60,
    sorter: (a: ScannerCandidate, b: ScannerCandidate) => a.score - b.score,
    defaultSortOrder: 'descend' as const,
  },
  {
    title: 'ADX',
    dataIndex: 'adx',
    key: 'adx',
    width: 70,
    render: (v: number) => v.toFixed(1),
    sorter: (a: ScannerCandidate, b: ScannerCandidate) => a.adx - b.adx,
  },
  {
    title: '20日涨幅',
    dataIndex: 'gain20',
    key: 'gain20',
    width: 90,
    render: (v: number) => <span style={{ color: v >= 0 ? '#52c41a' : '#f5222d' }}>{v >= 0 ? '+' : ''}{v.toFixed(1)}%</span>,
    sorter: (a: ScannerCandidate, b: ScannerCandidate) => a.gain20 - b.gain20,
  },
  {
    title: 'ATH跌幅',
    dataIndex: 'ath_drop',
    key: 'ath_drop',
    width: 90,
    render: (v: number) => <span style={{ color: '#fa541c' }}>-{v.toFixed(1)}%</span>,
    sorter: (a: ScannerCandidate, b: ScannerCandidate) => a.ath_drop - b.ath_drop,
  },
  {
    title: '均线',
    key: 'ma',
    width: 70,
    render: (_: any, r: ScannerCandidate) => r.bull_align ? <Tag color="green">多头</Tag> : r.bull_partial ? <Tag color="blue">偏多</Tag> : <Tag>空</Tag>,
  },
  {
    title: '放量比',
    dataIndex: 'vr',
    key: 'vr',
    width: 70,
    render: (v: number) => `${v.toFixed(1)}x`,
    sorter: (a: ScannerCandidate, b: ScannerCandidate) => a.vr - b.vr,
  },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    width: 90,
  },
  {
    title: '区域',
    dataIndex: 'zone',
    key: 'zone',
    width: 60,
    render: (v: string) => <Tag>{v}区</Tag>,
  },
];

const bottomColumns = [
  {
    title: '合约',
    dataIndex: 'pair',
    key: 'pair',
    width: 160,
    fixed: 'left' as const,
    render: (v: string) => <strong>{v.replace('_USDT', '').replace('-USDT', '').replace('USDT', '')}</strong>,
  },
  {
    title: 'AR',
    dataIndex: 'ar',
    key: 'ar',
    width: 90,
    render: (v: number) => v?.toFixed(5) ?? '-',
    sorter: (a: ScannerCandidate, b: ScannerCandidate) => (a.ar ?? 999) - (b.ar ?? 999),
    defaultSortOrder: 'ascend' as const,
  },
  {
    title: 'ATH跌幅',
    dataIndex: 'ath_drop',
    key: 'ath_drop',
    width: 90,
    render: (v: number) => <span style={{ color: '#fa541c' }}>-{v.toFixed(1)}%</span>,
    sorter: (a: ScannerCandidate, b: ScannerCandidate) => a.ath_drop - b.ath_drop,
  },
  {
    title: 'ADX',
    dataIndex: 'adx',
    key: 'adx',
    width: 70,
    render: (v: number) => v.toFixed(1),
  },
  {
    title: '均线',
    key: 'ma',
    width: 70,
    render: (_: any, r: ScannerCandidate) => r.bull_align ? <Tag color="green">多头</Tag> : r.bull_partial ? <Tag color="blue">偏多</Tag> : <Tag>空</Tag>,
  },
  {
    title: '状态',
    dataIndex: 'status',
    key: 'status',
    width: 90,
  },
];

export default function BottomTrendScanner() {
  const [exchange, setExchange] = useState('gate');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ScannerResult | null>(null);

  useEffect(() => {
    loadLatest();
  }, [exchange]);

  const loadLatest = async () => {
    try {
      const data = await bottomTrendScannerApi.getLatest(exchange);
      setResult(data);
    } catch {
      setResult(null);
    }
  };

  const handleScan = async () => {
    setLoading(true);
    try {
      const data = await bottomTrendScannerApi.scan(exchange);
      setResult(data);
      message.success(`扫描完成：${data.total_pairs} 个交易对，${data.trend_candidates.length} 个趋势候选，${data.bottom_candidates.length} 个底部候选`);
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '扫描失败');
    } finally {
      setLoading(false);
    }
  };

  const r = result;
  const trendData = r?.top_by_zone ? [
    ...(r.top_by_zone['A'] || []),
    ...(r.top_by_zone['B'] || []),
    ...(r.top_by_zone['C'] || []),
    ...(r.top_by_zone['D'] || []),
  ] : r?.all_candidates || [];

  return (
    <div style={{ padding: 24 }}>
      <h1>
        <ThunderboltOutlined /> 底部趋势扫描器
      </h1>
      <p style={{ color: '#666' }}>
        双策略量化扫描系统：策略1 底部横盘（AR≤1.008 + 跌幅≥50%）| 策略2 趋势追涨（ADX≥15 + 涨幅≥5%）
        ——支持 Gate.io 永续、Binance 现货、OKX 现货。
      </p>

      <Card style={{ marginBottom: 24 }}>
        <Row gutter={16} align="middle">
          <Col>
            <Select
              value={exchange}
              onChange={setExchange}
              options={EXCHANGES}
              style={{ width: 320 }}
            />
          </Col>
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
          {r && (
            <Col flex="auto" style={{ textAlign: 'right' }}>
              <span style={{ color: '#999', fontSize: 12 }}>
                上次扫描：{r.scan_time}  |  共 {r.total_pairs} 个交易对
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
                  title="趋势候选"
                  value={r.trend_candidates.length}
                  suffix={<RiseOutlined style={{ color: '#52c41a' }} />}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card>
                <Statistic
                  title="底部候选"
                  value={r.bottom_candidates.length}
                  suffix={<FallOutlined style={{ color: '#fa541c' }} />}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card>
                <Statistic
                  title="AAA 等级"
                  value={r.grades['AAA'] || 0}
                  valueStyle={{ color: '#f5222d' }}
                />
              </Card>
            </Col>
            <Col xs={12} sm={6}>
              <Card>
                <Statistic
                  title="横盘蓄力"
                  value={r.bottom_candidates.filter(b => b.status === '横盘蓄力').length}
                  suffix={<DotChartOutlined style={{ color: '#1890ff' }} />}
                />
              </Card>
            </Col>
          </Row>

          <Card style={{ marginBottom: 24 }}>
            <Row gutter={16}>
              {Object.entries(r.zones).map(([z, count]) => (
                <Col key={z} span={6}>
                  <Statistic
                    title={`${z}区 · ${ZONE_LABELS[z]}`}
                    value={count}
                  />
                </Col>
              ))}
            </Row>
          </Card>

          <Tabs
            defaultActiveKey="trend"
            items={[
              {
                key: 'trend',
                label: `📈 趋势候选 TOP (${trendData.length})`,
                children: (
                  <Table
                    dataSource={trendData}
                    columns={trendColumns}
                    rowKey="pair"
                    size="small"
                    scroll={{ x: 900 }}
                    pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 个` }}
                  />
                ),
              },
              {
                key: 'bottom',
                label: `📉 底部横盘 (${r.bottom_candidates.length})`,
                children: r.bottom_candidates.length > 0 ? (
                  <Table
                    dataSource={r.bottom_candidates}
                    columns={bottomColumns}
                    rowKey="pair"
                    size="small"
                    scroll={{ x: 600 }}
                    pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 个` }}
                  />
                ) : (
                  <Empty description="本次扫描无满足 AR≤1.008 且 跌幅≥50% 的标的" />
                ),
              },
              {
                key: 'aaa',
                label: `🔥 AAA 等级 (${r.grades['AAA'] || 0})`,
                children: (
                  <Table
                    dataSource={r.all_candidates.filter(c => c.grade === 'AAA')}
                    columns={trendColumns}
                    rowKey="pair"
                    size="small"
                    scroll={{ x: 900 }}
                    pagination={{ pageSize: 20, showTotal: (t) => `共 ${t} 个` }}
                  />
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
