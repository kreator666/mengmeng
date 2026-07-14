import { useEffect, useState } from 'react';
import { Card, Spin, Table, Tag, message } from 'antd';
import { factorApi } from '../../services/api';
import type { FactorInfo } from '../../types';

export default function FactorLibrary() {
  const [factors, setFactors] = useState<FactorInfo[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadFactors();
  }, []);

  const loadFactors = async () => {
    try {
      const data = await factorApi.getBuiltins();
      setFactors(data);
    } catch (err) {
      message.error('获取内置因子失败');
    } finally {
      setLoading(false);
    }
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <Tag color="blue">{text}</Tag>,
    },
    { title: '类别', dataIndex: 'category', key: 'category' },
    { title: '签名', dataIndex: 'signature', key: 'signature' },
    { title: '说明', dataIndex: 'description', key: 'description' },
  ];

  if (loading) {
    return (
      <div style={{ padding: 100, textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  return (
    <div style={{ padding: 24, maxWidth: 1200, margin: '0 auto' }}>
      <h1>因子库</h1>
      <Card>
        <Table dataSource={factors} columns={columns} rowKey="name" pagination={{ pageSize: 10 }} />
      </Card>
    </div>
  );
}
