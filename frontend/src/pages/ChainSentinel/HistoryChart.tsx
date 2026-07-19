import { useEffect, useRef } from 'react';
import { Card, Empty, Space, Table, Tag } from 'antd';
import dayjs from 'dayjs';
import * as echarts from 'echarts';
import type { SentinelEvent, SentinelHistoryItem } from '../../api/chainSentinel';
import { LIGHT_MAP } from './constants';

interface HistoryChartProps {
  history: SentinelHistoryItem[];
  events: SentinelEvent[];
}

export default function HistoryChart({ history, events }: HistoryChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current || history.length === 0) return;

    const chart = echarts.init(chartRef.current);
    // 灯色相对前一交易日变化的日期，用散点标出（颜色 = 新灯色）
    const changes = history
      .map((h, i) => ({ h, prev: i > 0 ? history[i - 1] : null }))
      .filter((x) => x.prev && x.prev.light !== x.h.light);

    chart.setOption({
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: history.map((h) => h.date) },
      yAxis: { type: 'value', name: '综合评分' },
      series: [
        {
          name: '综合评分',
          type: 'line',
          smooth: true,
          data: history.map((h) => h.total_score),
          areaStyle: { opacity: 0.1 },
        },
        {
          name: '灯色变化',
          type: 'scatter',
          symbolSize: 14,
          data: changes.map((x) => ({
            value: [x.h.date, x.h.total_score],
            itemStyle: { color: LIGHT_MAP[x.h.light].color },
          })),
        },
      ],
      dataZoom: [{ type: 'inside' }, { type: 'slider' }],
    });

    return () => {
      chart.dispose();
    };
  }, [history]);

  const eventColumns = [
    {
      title: '时间',
      dataIndex: 'ts',
      key: 'ts',
      render: (v: string) => dayjs(v).format('YYYY-MM-DD HH:mm'),
    },
    {
      title: '灯色变化',
      key: 'change',
      render: (_: unknown, e: SentinelEvent) => (
        <Space size={4}>
          {e.from_light ? (
            <Tag color={LIGHT_MAP[e.from_light].color}>{LIGHT_MAP[e.from_light].text}</Tag>
          ) : (
            <Tag>初始</Tag>
          )}
          <span>→</span>
          <Tag color={LIGHT_MAP[e.to_light].color}>{LIGHT_MAP[e.to_light].text}</Tag>
        </Space>
      ),
    },
    { title: '综合评分', dataIndex: 'total_score', key: 'total_score' },
    {
      title: '推送',
      dataIndex: 'notified',
      key: 'notified',
      render: (v: boolean) => (v ? <Tag color="green">已推送</Tag> : <Tag>未推送</Tag>),
    },
  ];

  return (
    <>
      <Card title="综合评分走势（散点 = 灯色变化日）" style={{ marginBottom: 24 }}>
        {history.length > 0 ? (
          <div ref={chartRef} style={{ width: '100%', height: 360 }} />
        ) : (
          <Empty description="暂无历史评分数据" />
        )}
      </Card>
      <Card title="灯色变化事件" style={{ marginBottom: 24 }}>
        <Table
          dataSource={events}
          columns={eventColumns}
          rowKey="id"
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: '暂无灯色变化事件' }}
        />
      </Card>
    </>
  );
}
