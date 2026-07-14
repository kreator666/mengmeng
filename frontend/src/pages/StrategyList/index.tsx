import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, List, Space, Spin, Tag, Typography, message } from 'antd';
import dayjs from 'dayjs';
import { backtestApi } from '../../services/api';
import type { BacktestResult } from '../../types';

const { Text } = Typography;

export default function StrategyList() {
  const navigate = useNavigate();
  const [results, setResults] = useState<BacktestResult[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadResults();
  }, []);

  const loadResults = async () => {
    setLoading(true);
    try {
      const data = await backtestApi.listBacktests(50);
      setResults(data);
    } catch (err) {
      message.error('获取回测历史失败');
    } finally {
      setLoading(false);
    }
  };

  const formatPct = (v: number) => `${(v * 100).toFixed(2)}%`;

  if (loading) {
    return (
      <div style={{ padding: 100, textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <h1>回测历史</h1>
      <Button type="primary" onClick={() => navigate('/')} style={{ marginBottom: 16 }}>
        新建回测
      </Button>

      <List
        grid={{ gutter: 16, column: 2 }}
        dataSource={results}
        locale={{ emptyText: '暂无回测记录' }}
        renderItem={(item) => (
          <List.Item>
            <Card
              title={
                <Space>
                  <span>{item.symbol}</span>
                  <Tag color="blue">{item.interval}</Tag>
                  <Tag color={item.market_type === 'spot' ? 'green' : 'orange'}>
                    {item.market_type === 'spot' ? '现货' : '合约'}
                  </Tag>
                </Space>
              }
              extra={
                <Button type="link" onClick={() => navigate(`/result/${item.id}`)}>
                  查看详情
                </Button>
              }
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                <div>
                  <Text type="secondary">时间范围：</Text>
                  <Text>
                    {item.from_date?.slice(0, 10)} ~ {item.to_date?.slice(0, 10)}
                  </Text>
                </div>
                <div>
                  <Text type="secondary">总收益：</Text>
                  <Text
                    type={item.summary.total_return >= 0 ? 'success' : 'danger'}
                    strong
                  >
                    {formatPct(item.summary.total_return)}
                  </Text>
                </div>
                <div>
                  <Text type="secondary">最大回撤：</Text>
                  <Text type="danger">{formatPct(item.summary.max_drawdown)}</Text>
                </div>
                <div>
                  <Text type="secondary">交易次数：</Text>
                  <Text>{item.summary.total_trades}</Text>
                </div>
                <div>
                  <Text type="secondary">胜率：</Text>
                  <Text>{formatPct(item.summary.win_rate)}</Text>
                </div>
                <div>
                  <Text type="secondary">夏普比率：</Text>
                  <Text>{item.summary.sharpe_ratio.toFixed(2)}</Text>
                </div>
                <div>
                  <Text type="secondary">回测时间：</Text>
                  <Text>{item.created_at ? dayjs(item.created_at).format('YYYY-MM-DD HH:mm') : '-'}</Text>
                </div>
              </Space>
            </Card>
          </List.Item>
        )}
      />
    </div>
  );
}
