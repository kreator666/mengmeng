import { useEffect, useRef, useState } from 'react';
import { useParams } from 'react-router-dom';
import { Card, Col, Row, Spin, Statistic, Table, message } from 'antd';
import * as echarts from 'echarts';
import { createChart, ColorType, type Time } from 'lightweight-charts';
import { backtestApi, dataApi } from '../../services/api';
import type { BacktestResult, KlineData, TradeRecord } from '../../types';

export default function BacktestResult() {
  const { id } = useParams<{ id: string }>();
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [klines, setKlines] = useState<KlineData[]>([]);
  const [loading, setLoading] = useState(true);

  const equityChartRef = useRef<HTMLDivElement>(null);
  const drawdownChartRef = useRef<HTMLDivElement>(null);
  const klineChartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!id) return;
    loadResult();
  }, [id]);

  useEffect(() => {
    if (!result) return;
    loadKlines();
  }, [result]);

  useEffect(() => {
    if (!result || !equityChartRef.current || !drawdownChartRef.current) return;

    const equityChart = echarts.init(equityChartRef.current);
    equityChart.setOption({
      title: { text: '资金曲线' },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: result.equity_curve.map((d) => d.timestamp) },
      yAxis: { type: 'value' },
      series: [
        {
          name: '资金',
          type: 'line',
          data: result.equity_curve.map((d) => d.equity),
          smooth: true,
          areaStyle: { opacity: 0.2 },
        },
      ],
      dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    });

    const drawdownChart = echarts.init(drawdownChartRef.current);
    drawdownChart.setOption({
      title: { text: '回撤分析' },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: result.drawdown_series.map((d) => d.timestamp) },
      yAxis: { type: 'value', axisLabel: { formatter: '{value}%' } },
      series: [
        {
          name: '回撤',
          type: 'line',
          data: result.drawdown_series.map((d) => d.drawdown * 100),
          areaStyle: { color: '#ff4d4f', opacity: 0.3 },
          lineStyle: { color: '#ff4d4f' },
        },
      ],
      dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    });

    return () => {
      equityChart.dispose();
      drawdownChart.dispose();
    };
  }, [result]);

  useEffect(() => {
    if (!klines.length || !klineChartRef.current) return;

    const chart = createChart(klineChartRef.current, {
      layout: { background: { type: ColorType.Solid, color: '#ffffff' }, textColor: '#333' },
      width: klineChartRef.current.clientWidth,
      height: 400,
    });

    const candlestickSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderVisible: false,
      wickUpColor: '#26a69a',
      wickDownColor: '#ef5350',
    });

    candlestickSeries.setData(
      klines.map((k) => ({
        time: new Date(k.timestamp).getTime() / 1000 as Time,
        open: k.open,
        high: k.high,
        low: k.low,
        close: k.close,
      }))
    );

    const markers = result?.trades.map((t) => ({
      time: new Date(t.entry_time).getTime() / 1000 as Time,
      position: (t.side === 'long' ? 'belowBar' : 'aboveBar') as 'belowBar' | 'aboveBar',
      color: t.side === 'long' ? '#26a69a' : '#ef5350',
      shape: (t.side === 'long' ? 'arrowUp' : 'arrowDown') as 'arrowUp' | 'arrowDown',
      text: t.side === 'long' ? '买' : '卖',
    }));

    if (markers) {
      candlestickSeries.setMarkers(markers);
    }

    chart.timeScale().fitContent();

    return () => {
      chart.remove();
    };
  }, [klines]);

  const loadResult = async () => {
    try {
      const data = await backtestApi.getBacktest(id!);
      setResult(data);
    } catch (err) {
      message.error('获取回测结果失败');
    } finally {
      setLoading(false);
    }
  };

  const loadKlines = async () => {
    if (!result) return;
    try {
      const trades = result.trades;
      if (!trades.length) {
        // 没有交易记录时，使用回测的完整时间范围
        const data = await dataApi.getKlines({
          symbol: result.symbol,
          interval: result.interval,
          market_type: result.market_type,
          provider: result.provider || 'gateio',
          from: result.from_date.slice(0, 10),
          to: result.to_date.slice(0, 10),
        });
        setKlines(data);
        return;
      }

      const start = trades[0].entry_time.slice(0, 10);
      const end = trades[trades.length - 1].exit_time.slice(0, 10);
      const data = await dataApi.getKlines({
        symbol: result.symbol,
        interval: result.interval,
        market_type: result.market_type,
        provider: result.provider || 'gateio',
        from: start,
        to: end,
      });
      setKlines(data);
    } catch (err) {
      console.error('获取K线数据失败', err);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: 100, textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!result) {
    return <div style={{ padding: 24 }}>回测结果不存在</div>;
  }

  const s = result.summary;

  const columns = [
    { title: '入场时间', dataIndex: 'entry_time', key: 'entry_time' },
    { title: '出场时间', dataIndex: 'exit_time', key: 'exit_time' },
    { title: '方向', dataIndex: 'side', key: 'side' },
    { title: '入场价', dataIndex: 'entry_price', key: 'entry_price' },
    { title: '出场价', dataIndex: 'exit_price', key: 'exit_price' },
    {
      title: '收益率',
      dataIndex: 'return_pct',
      key: 'return_pct',
      render: (v: number) => `${(v * 100).toFixed(2)}%`,
    },
  ];

  const formatPct = (v: number) => `${(v * 100).toFixed(2)}%`;

  return (
    <div style={{ padding: 24 }}>
      <h1>回测结果</h1>

      <Card title="回测信息" style={{ marginBottom: 24 }}>
        <Row gutter={[16, 16]}>
          <Col span={6}>
            <Statistic title="交易对" value={result.symbol} />
          </Col>
          <Col span={6}>
            <Statistic title="行情源" value={result.provider || 'gateio'} />
          </Col>
          <Col span={6}>
            <Statistic title="市场类型" value={result.market_type === 'spot' ? '现货' : '合约'} />
          </Col>
          <Col span={6}>
            <Statistic title="周期" value={result.interval} />
          </Col>
          <Col span={12}>
            <Statistic
              title="时间范围"
              value={`${result.from_date.slice(0, 10)} ~ ${result.to_date.slice(0, 10)}`}
            />
          </Col>
        </Row>
      </Card>

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card>
            <Statistic title="总收益率" value={formatPct(s.total_return)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="年化收益率" value={formatPct(s.annualized_return)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="最大回撤" value={formatPct(s.max_drawdown)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="夏普比率" value={s.sharpe_ratio.toFixed(2)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="索提诺比率" value={s.sortino_ratio.toFixed(2)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="Calmar 比率" value={s.calmar_ratio.toFixed(2)} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="交易次数" value={s.total_trades} />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="胜率" value={formatPct(s.win_rate)} />
          </Card>
        </Col>
      </Row>

      <Card title="资金曲线" style={{ marginBottom: 24 }}>
        <div ref={equityChartRef} style={{ width: '100%', height: 400 }} />
      </Card>

      <Card title="回撤分析" style={{ marginBottom: 24 }}>
        <div ref={drawdownChartRef} style={{ width: '100%', height: 300 }} />
      </Card>

      <Card title="K线叠加买卖点" style={{ marginBottom: 24 }}>
        <div ref={klineChartRef} style={{ width: '100%', height: 400 }} />
      </Card>

      <Card title="交易记录">
        <Table
          dataSource={result.trades}
          columns={columns}
          rowKey={(record: TradeRecord) => `${record.entry_time}-${record.exit_time}`}
          pagination={{ pageSize: 10 }}
        />
      </Card>
    </div>
  );
}
