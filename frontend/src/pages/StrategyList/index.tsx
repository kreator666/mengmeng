import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Card, List, Spin, message } from 'antd';
import { strategyApi } from '../../services/api';

export default function StrategyList() {
  const navigate = useNavigate();
  const [strategies, setStrategies] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadStrategies();
  }, []);

  const loadStrategies = async () => {
    try {
      const data = await strategyApi.listStrategies();
      setStrategies(data);
    } catch (err) {
      message.error('获取策略列表失败');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: 100, textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <h1>策略列表</h1>
      <Button type="primary" onClick={() => navigate('/')} style={{ marginBottom: 16 }}>
        新建策略
      </Button>

      <List
        grid={{ gutter: 16, column: 3 }}
        dataSource={strategies}
        locale={{ emptyText: '暂无策略' }}
        renderItem={(item) => (
          <List.Item>
            <Card title={item.name}>
              <p>{item.description || '暂无描述'}</p>
              <Button type="link" onClick={() => navigate(`/`)}>
                编辑
              </Button>
            </Card>
          </List.Item>
        )}
      />
    </div>
  );
}
