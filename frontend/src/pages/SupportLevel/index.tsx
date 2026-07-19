import { useEffect, useRef, useState } from 'react';
import { Alert, AutoComplete, Button, Card, Checkbox, Col, Collapse, DatePicker, Form, InputNumber, Radio, Row, Select, Space, Spin, Statistic, Table, Tag, message } from 'antd';
import dayjs, { type Dayjs } from 'dayjs';
import { createChart, ColorType, LineStyle, type Time, type SeriesMarker } from 'lightweight-charts';
import { dataApi, fibApi, supportLevelApi } from '../../services/api';
import type { FibLevelsResult, KlineData, SupportLevelAnalyzeResult, SupportLevelEvent, SymbolInfo } from '../../types';

const { RangePicker } = DatePicker;

const INTERVAL_OPTIONS = [
  { label: '1小时', value: '1h' },
  { label: '2小时', value: '2h' },
  { label: '4小时', value: '4h' },
  { label: '日线', value: '1d' },
  { label: '3日', value: '3d' },
  { label: '周线', value: '7d' },
  { label: '月线', value: '30d' },
  { label: '季线', value: '3M' },
];

const MARKET_TYPES = [
  { value: 'futures_usdt', label: 'USDT 合约' },
  { value: 'spot', label: '现货' },
  { value: 'us_stock', label: '美股' },
];

// 美股数据源只支持日/周/月/季
const US_STOCK_INTERVALS = ['1d', '7d', '30d', '3M'];

const isUsStock = (marketType: string) => marketType === 'us_stock';
const toProvider = (marketType: string) => (isUsStock(marketType) ? 'us_stock' : 'gateio');
const toApiMarketType = (marketType: string) => (isUsStock(marketType) ? 'spot' : marketType);

const FIB_PERIOD_OPTIONS = [
  { label: '周线', value: '7d' },
  { label: '月线', value: '30d' },
];

const STATUS_MAP: Record<SupportLevelEvent['status'], { color: string; text: string }> = {
  bounced: { color: 'green', text: '反弹成功' },
  broke: { color: 'red', text: '支撑破位' },
  flat: { color: 'default', text: '未反弹' },
  pending: { color: 'gold', text: '待定' },
};

interface FormValues {
  symbol: string;
  market_type: string;
  interval: string;
  dates: [Dayjs, Dayjs];
  lookback: number;
  bounce_bars: number;
  bounce_threshold: number;
  breakout_factor: number;
  fib_low?: number;
  fib_high?: number;
}

export default function SupportLevel() {
  const [form] = Form.useForm<FormValues>();
  const marketType = Form.useWatch('market_type', form) ?? 'futures_usdt';
  const selectedSymbol = Form.useWatch('symbol', form) ?? 'BTC_USDT';
  const [symbols, setSymbols] = useState<SymbolInfo[]>([]);
  const [result, setResult] = useState<SupportLevelAnalyzeResult | null>(null);
  const [klines, setKlines] = useState<KlineData[]>([]);
  const [loading, setLoading] = useState(false);
  const [showSupport, setShowSupport] = useState(true);
  const [showFib, setShowFib] = useState(false);
  const [fibPeriod, setFibPeriod] = useState<string>('7d');
  const [fibData, setFibData] = useState<FibLevelsResult | null>(null);
  const [fibLoading, setFibLoading] = useState(false);
  const chartRef = useRef<HTMLDivElement>(null);

  // 当前品种的价格精度（交易所小数位），未匹配到时退回 4 位
  const precision = symbols.find((s2) => s2.symbol === selectedSymbol)?.price_precision ?? 4;
  const fmtPrice = (v: number) => v.toFixed(precision);
  const minMove = Math.pow(10, -precision);

  const loadSymbols = async (marketType?: string) => {
    const currentMarketType = marketType || form.getFieldValue('market_type') || 'futures_usdt';
    try {
      const data = await dataApi.getSymbols(toApiMarketType(currentMarketType), toProvider(currentMarketType));
      // 将主流交易对置顶，其余按字母顺序排序
      const prioritized = ['BTC_USDT', 'ETH_USDT', 'SOXL'];
      const sorted = [...data].sort((a, b) => {
        const idxA = prioritized.indexOf(a.symbol);
        const idxB = prioritized.indexOf(b.symbol);
        if (idxA !== -1 && idxB !== -1) return idxA - idxB;
        if (idxA !== -1) return -1;
        if (idxB !== -1) return 1;
        return a.symbol.localeCompare(b.symbol);
      });
      setSymbols(sorted);
    } catch {
      message.error('获取交易对列表失败');
    }
  };

  useEffect(() => {
    loadSymbols();
  }, []);

  const handleMarketTypeChange = async (marketType: string) => {
    form.setFieldsValue({ symbol: undefined });
    // 美股只支持日/周/月/季，当前周期不支持时重置为日线
    if (isUsStock(marketType)) {
      const current = form.getFieldValue('interval');
      if (!US_STOCK_INTERVALS.includes(current)) {
        form.setFieldsValue({ interval: '1d' });
      }
    }
    await loadSymbols(marketType);
  };

  const loadFib = async (period?: string) => {
    const values = form.getFieldsValue();
    if (!values.symbol) return;
    setFibLoading(true);
    try {
      const data = await fibApi.getFibLevels({
        symbol: values.symbol,
        interval: period || fibPeriod,
        market_type: toApiMarketType(values.market_type),
        provider: toProvider(values.market_type),
        breakout_factor: values.breakout_factor,
        ...(values.fib_low != null && values.fib_high != null
          ? { fib_low: values.fib_low, fib_high: values.fib_high }
          : {}),
      });
      setFibData(data);
    } catch (err: any) {
      setFibData(null);
      message.error(err?.response?.data?.detail || '斐波数据获取失败');
    } finally {
      setFibLoading(false);
    }
  };

  const handleShowFibChange = async (checked: boolean) => {
    setShowFib(checked);
    if (checked && !fibData && result) {
      await loadFib();
    }
  };

  const handleFibPeriodChange = async (period: string) => {
    setFibPeriod(period);
    if (showFib) {
      await loadFib(period);
    }
  };

  useEffect(() => {
    if (!result || !klines.length || !chartRef.current) return;

    const chart = createChart(chartRef.current, {
      layout: { background: { type: ColorType.Solid, color: '#ffffff' }, textColor: '#333' },
      width: chartRef.current.clientWidth,
      height: 480,
    });

    const toTime = (ts: string) => (new Date(ts).getTime() / 1000) as Time;

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: false,
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
      priceFormat: { type: 'price', precision, minMove },
    });
    candlestickSeries.setData(
      klines.map((k) => ({
        time: toTime(k.timestamp),
        open: k.open,
        high: k.high,
        low: k.low,
        close: k.close,
      }))
    );

    // 支撑位线（可勾选显示）
    if (showSupport) {
      const supportSeries = chart.addLineSeries({
        color: '#fa8c16',
        lineWidth: 2,
        title: '支撑位',
        priceFormat: { type: 'price', precision, minMove },
      });
      supportSeries.setData(result.points.map((p) => ({ time: toTime(p.timestamp), value: p.support })));
    }

    // 事件标记
    const markers: SeriesMarker<Time>[] = result.events.map((e) => {
      const time = toTime(e.timestamp);
      if (e.status === 'bounced') {
        return {
          time,
          position: 'belowBar',
          color: '#26a69a',
          shape: 'arrowUp',
          text: `反弹 +${(e.max_bounce_pct * 100).toFixed(1)}%`,
        };
      }
      if (e.status === 'broke') {
        return { time, position: 'aboveBar', color: '#ef5350', shape: 'arrowDown', text: '破位' };
      }
      if (e.status === 'flat') {
        return { time, position: 'belowBar', color: '#8c8c8c', shape: 'circle', text: '未反弹' };
      }
      return { time, position: 'belowBar', color: '#faad14', shape: 'circle', text: '待定' };
    });
    markers.sort((a, b) => (a.time as number) - (b.time as number));
    candlestickSeries.setMarkers(markers);

    // 斐波扩展水平线（只画可见档位：区间内全部 + 当前价附近的扩展档）
    if (showFib && fibData) {
      for (const level of fibData.levels) {
        if (!level.visible) continue;
        const isRange = level.kind === 'range';
        candlestickSeries.createPriceLine({
          price: level.price,
          color: isRange ? '#2f54eb' : '#722ed1',
          lineWidth: isRange ? 1 : 2,
          lineStyle: isRange ? LineStyle.Dashed : LineStyle.Solid,
          axisLabelVisible: true,
          title: `${level.ratio} (${fmtPrice(level.price)})`,
        });
      }
    }

    chart.timeScale().fitContent();

    return () => {
      chart.remove();
    };
  }, [result, klines, showSupport, showFib, fibData, precision, minMove]);

  const onFinish = async (values: FormValues) => {
    setLoading(true);
    setResult(null);
    setFibData(null);
    try {
      const params = {
        symbol: values.symbol,
        interval: values.interval,
        market_type: toApiMarketType(values.market_type),
        provider: toProvider(values.market_type),
        from: values.dates[0].format('YYYY-MM-DD'),
        to: values.dates[1].format('YYYY-MM-DD'),
        lookback: values.lookback,
        bounce_bars: values.bounce_bars,
        bounce_threshold: values.bounce_threshold / 100,
      };
      const [analyzeResult, klineData] = await Promise.all([
        supportLevelApi.analyze(params),
        dataApi.getKlines(params),
      ]);
      setResult(analyzeResult);
      setKlines(klineData);
      if (showFib) {
        await loadFib();
      }
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '分析失败');
    } finally {
      setLoading(false);
    }
  };

  const formatPct = (v: number | null) => (v === null ? '-' : `${(v * 100).toFixed(2)}%`);
  const formatPrice = (v: number | null) => (v === null ? '-' : v.toFixed(precision));
  const formatDate = (v: string | null) => (v ? dayjs(v).format('YYYY-MM-DD') : '-');

  const eventColumns = [
    {
      title: '回踩时间',
      dataIndex: 'timestamp',
      key: 'timestamp',
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    { title: '支撑位', dataIndex: 'support', key: 'support', render: (v: number) => v.toFixed(precision) },
    { title: '回踩低点', dataIndex: 'touch_low', key: 'touch_low', render: (v: number) => v.toFixed(precision) },
    {
      title: '最大反弹',
      dataIndex: 'max_bounce_pct',
      key: 'max_bounce_pct',
      render: (v: number) => `${(v * 100).toFixed(2)}%`,
    },
    {
      title: '结果',
      dataIndex: 'status',
      key: 'status',
      render: (v: SupportLevelEvent['status']) => <Tag color={STATUS_MAP[v].color}>{STATUS_MAP[v].text}</Tag>,
    },
  ];

  const s = result?.stats;
  const fr = fibData?.range;

  return (
    <div style={{ padding: 24 }}>
      <h1>支撑位分析</h1>
      <p style={{ color: '#666' }}>
        支撑位 = (区间高点 − 区间低点) / 3 + 区间低点。强势股回踩该支撑位大概率反弹，图中橙色线为动态支撑位，箭头标记历史回踩事件。
        斐波扩展：price(k) = 区间低点 + k × (区间高点 − 区间低点)，蓝色虚线为区间内档位（0~1），紫色实线为扩展档位（1.618~377，仅显示当前价附近 7 条）。
      </p>

      <Card style={{ marginBottom: 24 }}>
        <Form
          form={form}
          onFinish={onFinish}
          initialValues={{
            symbol: 'BTC_USDT',
            market_type: 'futures_usdt',
            interval: '1d',
            dates: [dayjs().subtract(120, 'day'), dayjs()],
            lookback: 60,
            bounce_bars: 10,
            bounce_threshold: 5,
            breakout_factor: 1.5,
          }}
        >
          <Space size="middle" wrap>
            <Form.Item name="market_type" label="市场类型" rules={[{ required: true }]} style={{ marginBottom: 8 }}>
              <Select style={{ width: 120 }} options={MARKET_TYPES} onChange={handleMarketTypeChange} />
            </Form.Item>
            <Form.Item name="symbol" label="交易对" rules={[{ required: true }]} style={{ marginBottom: 8 }}>
              {isUsStock(marketType) ? (
                <AutoComplete
                  style={{ width: 180 }}
                  placeholder="输入 ticker，如 SOXL"
                  options={symbols.map((s) => ({ label: s.symbol, value: s.symbol }))}
                  filterOption={(input, option) =>
                    (option?.value as string).toUpperCase().includes(input.toUpperCase())
                  }
                />
              ) : (
                <Select
                  showSearch
                  style={{ width: 180 }}
                  options={symbols.map((s) => ({ label: s.symbol, value: s.symbol }))}
                />
              )}
            </Form.Item>
            <Form.Item name="interval" label="周期" rules={[{ required: true }]} style={{ marginBottom: 8 }}>
              <Select
                style={{ width: 100 }}
                options={
                  isUsStock(marketType)
                    ? INTERVAL_OPTIONS.filter((i) => US_STOCK_INTERVALS.includes(i.value))
                    : INTERVAL_OPTIONS
                }
              />
            </Form.Item>
            <Form.Item name="dates" label="时间范围" rules={[{ required: true }]} style={{ marginBottom: 8 }}>
              <RangePicker />
            </Form.Item>
            <Form.Item style={{ marginBottom: 8 }}>
              <Button type="primary" htmlType="submit" loading={loading}>
                分析
              </Button>
            </Form.Item>
            <Form.Item style={{ marginBottom: 8 }}>
              <Checkbox checked={showSupport} onChange={(e) => setShowSupport(e.target.checked)}>
                显示支撑位
              </Checkbox>
            </Form.Item>
            <Form.Item style={{ marginBottom: 8 }}>
              <Checkbox checked={showFib} onChange={(e) => handleShowFibChange(e.target.checked)}>
                显示斐波扩展
              </Checkbox>
            </Form.Item>
            {showFib && (
              <Form.Item style={{ marginBottom: 8 }}>
                <Radio.Group
                  value={fibPeriod}
                  onChange={(e) => handleFibPeriodChange(e.target.value)}
                  options={FIB_PERIOD_OPTIONS}
                  optionType="button"
                  size="small"
                />
              </Form.Item>
            )}
          </Space>
          <Collapse
            items={[
              {
                key: 'advanced',
                label: '高级参数',
                children: (
                  <Space size="large" wrap>
                    <span>
                      区间窗口：
                      <Form.Item name="lookback" noStyle>
                        <InputNumber min={5} max={500} style={{ width: 80 }} />
                      </Form.Item>
                      根
                    </span>
                    <span>
                      反弹判定：
                      <Form.Item name="bounce_bars" noStyle>
                        <InputNumber min={1} max={200} style={{ width: 70 }} />
                      </Form.Item>
                      根内涨幅 ≥
                      <Form.Item name="bounce_threshold" noStyle>
                        <InputNumber min={0.5} max={100} step={0.5} style={{ width: 70 }} />
                      </Form.Item>
                      %
                    </span>
                    <span>
                      斐波突破倍数：
                      <Form.Item name="breakout_factor" noStyle>
                        <InputNumber min={1.1} max={5} step={0.1} style={{ width: 70 }} />
                      </Form.Item>
                    </span>
                    <span>
                      手动区间（可选）：低
                      <Form.Item name="fib_low" noStyle>
                        <InputNumber min={0} placeholder="自动" style={{ width: 100 }} />
                      </Form.Item>
                      高
                      <Form.Item name="fib_high" noStyle>
                        <InputNumber min={0} placeholder="自动" style={{ width: 100 }} />
                      </Form.Item>
                      （重新点“分析”生效）
                    </span>
                  </Space>
                ),
              },
            ]}
          />
        </Form>
      </Card>

      {loading && (
        <div style={{ padding: 60, textAlign: 'center' }}>
          <Spin size="large" />
        </div>
      )}

      {result && s && (
        <>
          {result.points.length === 0 && (
            <Alert
              style={{ marginBottom: 24 }}
              type="warning"
              showIcon
              message="数据不足以计算支撑位"
              description="当前时间范围内的 K 线数量少于区间窗口（lookback），请扩大时间范围，或在“高级参数”中调小区间窗口。大周期（如季线）建议窗口设为 8~20。"
            />
          )}
          <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
            <Col span={6}>
              <Card>
                <Statistic title="当前支撑位" value={formatPrice(s.current_support)} />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="现价距支撑" value={formatPct(s.distance_to_support_pct)} />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="历史回踩次数" value={s.total_touches} />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="反弹成功次数" value={s.bounced_count} />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="反弹成功率" value={formatPct(s.success_rate)} />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="平均最大反弹" value={formatPct(s.avg_bounce_pct)} />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="最大单次反弹" value={formatPct(s.max_bounce_pct)} />
              </Card>
            </Col>
            <Col span={6}>
              <Card>
                <Statistic title="破位次数" value={s.broke_count} />
              </Card>
            </Col>
          </Row>

          {showFib && fibData && fr && (
            <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
              <Col span={6}>
                <Card>
                  <Statistic title={`斐波区间低点（0）`} value={fr.range_low.toFixed(precision)} />
                </Card>
              </Col>
              <Col span={6}>
                <Card>
                  <Statistic title={`斐波区间高点（1）`} value={fr.range_high.toFixed(precision)} />
                </Card>
              </Col>
              <Col span={6}>
                <Card>
                  <Statistic title="区间确认周期" value={fibData.interval === '7d' ? '周线' : '月线'} />
                </Card>
              </Col>
              <Col span={6}>
                <Card>
                  <Statistic title="脱离区间时间" value={formatDate(fr.breakout_time)} />
                </Card>
              </Col>
            </Row>
          )}
          {showFib && fibLoading && (
            <div style={{ marginBottom: 16, color: '#666' }}>
              <Spin size="small" /> 正在计算斐波扩展（需拉取周线/月线全历史，首次较慢）...
            </div>
          )}

          <Card title="K线 · 支撑位 · 回踩事件 · 斐波扩展" style={{ marginBottom: 24 }}>
            <div ref={chartRef} style={{ width: '100%', height: 480 }} />
          </Card>

          <Card title="回踩事件明细">
            <Table
              dataSource={result.events}
              columns={eventColumns}
              rowKey={(r: SupportLevelEvent) => r.timestamp}
              pagination={{ pageSize: 10 }}
            />
          </Card>
        </>
      )}
    </div>
  );
}
