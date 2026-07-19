import { useEffect, useRef } from 'react';
import { Card, Divider, Empty, Table, Tag } from 'antd';
import * as echarts from 'echarts';
import type { SentinelHistoryItem, SentinelMember } from '../../api/chainSentinel';

interface PricePanelProps {
  members: SentinelMember[] | null;
  history: SentinelHistoryItem[];
}

const scoreColor = (v: number) => (v >= 70 ? '#ff4d4f' : v >= 40 ? '#fa8c16' : '#52c41a');

export default function PricePanel({ members, history }: PricePanelProps) {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!chartRef.current || history.length === 0) return;

    const chart = echarts.init(chartRef.current);
    chart.setOption({
      tooltip: { trigger: 'axis' },
      grid: { left: 48, right: 16, top: 32, bottom: 28 },
      xAxis: { type: 'category', data: history.map((h) => h.date) },
      yAxis: { type: 'value', name: '价格层评分' },
      series: [
        {
          name: '价格层评分',
          type: 'line',
          smooth: true,
          data: history.map((h) => h.price_score),
          areaStyle: { opacity: 0.1 },
        },
      ],
    });

    return () => {
      chart.dispose();
    };
  }, [history]);

  const columns = [
    { title: '代码', dataIndex: 'symbol', key: 'symbol' },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: '风险评分',
      dataIndex: 'risk_score',
      key: 'risk_score',
      sorter: (a: SentinelMember, b: SentinelMember) => a.risk_score - b.risk_score,
      render: (v: number) => <span style={{ color: scoreColor(v), fontWeight: 600 }}>{v}</span>,
    },
    {
      title: '命中理由',
      dataIndex: 'reasons',
      key: 'reasons',
      render: (items: string[]) =>
        items.length ? (
          <ul style={{ margin: 0, paddingLeft: 16 }}>
            {items.map((r, i) => (
              <li key={i}>{r}</li>
            ))}
          </ul>
        ) : (
          '-'
        ),
    },
  ];

  return (
    <Card title="价格层 · 成员风险明细" style={{ height: '100%' }}>
      {members === null ? (
        <Empty description="点击立即扫描获取成员明细" />
      ) : (
        <Table dataSource={members} columns={columns} rowKey="symbol" pagination={false} size="small" />
      )}
      {history.length > 0 && (
        <>
          <Divider style={{ margin: '12px 0' }} />
          <div ref={chartRef} style={{ width: '100%', height: 180 }} />
        </>
      )}
    </Card>
  );
}
