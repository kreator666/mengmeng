import { useEffect, useState } from 'react';
import {
  Button,
  Card,
  Form,
  Input,
  Modal,
  Popconfirm,
  Radio,
  Space,
  Spin,
  Table,
  Tag,
  Typography,
  message,
} from 'antd';
import { factorApi } from '../../services/api';
import type { CustomFactor, FactorInfo } from '../../types';

const { TextArea } = Input;
const { Paragraph, Text } = Typography;

export default function FactorLibrary() {
  const [builtinFactors, setBuiltinFactors] = useState<FactorInfo[]>([]);
  const [customFactors, setCustomFactors] = useState<CustomFactor[]>([]);
  const [loading, setLoading] = useState(true);
  const [modalVisible, setModalVisible] = useState(false);
  const [viewFactor, setViewFactor] = useState<CustomFactor | null>(null);
  const [viewVisible, setViewVisible] = useState(false);
  const [form] = Form.useForm();
  const [submitting, setSubmitting] = useState(false);

  // 监听模式变化，用于动态切换代码输入框标签和 placeholder
  const modeValue = Form.useWatch('mode', form);
  const isFormulaMode = modeValue === 'formula';
  const codeLabel = isFormulaMode ? '公式表达式' : 'Python 代码';
  const codePlaceholder = isFormulaMode
    ? '例如：EMA(close, 12) > EMA(close, 26)'
    : "def factor(df):\n    # 返回 pandas.Series，正值做多，负值做空\n    ...";

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      // 优先使用统一接口；若后端未更新，则回退到分别调用
      try {
        const library = await factorApi.getFactorLibrary();
        setBuiltinFactors(library.builtins || []);
        setCustomFactors(library.custom || []);
      } catch (err) {
        const [builtins, customs] = await Promise.all([
          factorApi.getBuiltins(),
          factorApi.getCustomFactors(),
        ]);
        setBuiltinFactors(builtins || []);
        setCustomFactors(customs || []);
      }
    } catch (err) {
      message.error('获取因子库失败，请确认后端服务已启动');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (values: any) => {
    setSubmitting(true);
    try {
      await factorApi.createCustomFactor({
        name: values.name,
        category: values.category || '自定义',
        description: values.description || '',
        mode: values.mode,
        code: values.code,
      });
      message.success('创建成功');
      setModalVisible(false);
      form.resetFields();
      loadData();
    } catch (err: any) {
      message.error(err.response?.data?.detail || '创建失败');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await factorApi.deleteCustomFactor(id);
      message.success('删除成功');
      loadData();
    } catch (err: any) {
      message.error(err.response?.data?.detail || '删除失败');
    }
  };

  const handleView = async (factor: CustomFactor) => {
    try {
      const data = await factorApi.getCustomFactor(factor.id);
      setViewFactor(data);
      setViewVisible(true);
    } catch (err: any) {
      message.error(err.response?.data?.detail || '获取因子详情失败');
    }
  };

  const builtinColumns = [
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

  const customColumns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string) => <Tag color="green">{text}</Tag>,
    },
    { title: '模式', dataIndex: 'mode', key: 'mode' },
    { title: '类别', dataIndex: 'category', key: 'category' },
    { title: '说明', dataIndex: 'description', key: 'description' },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: CustomFactor) => (
        <Space>
          <Button size="small" onClick={() => handleView(record)}>
            查看
          </Button>
          <Popconfirm
            title="确认删除"
            description={`确定删除因子 "${record.name}" 吗？`}
            onConfirm={() => handleDelete(record.id)}
            okText="删除"
            cancelText="取消"
          >
            <Button danger size="small">
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
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

      <Card title="内置因子" style={{ marginBottom: 24 }}>
        <Table
          dataSource={builtinFactors}
          columns={builtinColumns}
          rowKey="name"
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: '暂无内置因子' }}
        />
      </Card>

      <Card
        title="自定义因子"
        extra={
          <Button type="primary" onClick={() => setModalVisible(true)}>
            新建因子
          </Button>
        }
        style={{ marginBottom: 24 }}
      >
        <Table
          dataSource={customFactors}
          columns={customColumns}
          rowKey="id"
          pagination={{ pageSize: 10 }}
          locale={{ emptyText: '暂无自定义因子，点击右上角新建' }}
        />
      </Card>

      <Modal
        title="新建自定义因子"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        width={720}
        destroyOnClose
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreate}
          initialValues={{ category: '自定义', mode: 'python' }}
        >
          <Form.Item
            label="因子名称"
            name="name"
            rules={[{ required: true, message: '请输入因子名称' }]}
          >
            <Input placeholder="例如：恐慌抄底" />
          </Form.Item>

          <Form.Item label="模式" name="mode" rules={[{ required: true }]}>
            <Radio.Group>
              <Radio value="python">Python 代码</Radio>
              <Radio value="formula">公式表达式</Radio>
            </Radio.Group>
          </Form.Item>

          <Form.Item label="类别" name="category">
            <Input placeholder="自定义" />
          </Form.Item>

          <Form.Item label="说明" name="description">
            <Input placeholder="简要描述因子逻辑" />
          </Form.Item>

          <Form.Item
            label={codeLabel}
            name="code"
            rules={[{ required: true, message: '请输入因子代码' }]}
          >
            <TextArea rows={16} placeholder={codePlaceholder} />
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={submitting}>
                保存
              </Button>
              <Button onClick={() => setModalVisible(false)}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title={viewFactor ? viewFactor.name : '因子详情'}
        open={viewVisible}
        onCancel={() => setViewVisible(false)}
        footer={[
          <Button key="close" onClick={() => setViewVisible(false)}>
            关闭
          </Button>,
        ]}
        width={720}
      >
        {viewFactor && (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <div>
              <Text strong>模式：</Text>
              <Tag color={viewFactor.mode === 'python' ? 'blue' : 'green'}>{viewFactor.mode}</Tag>
            </div>
            <div>
              <Text strong>类别：</Text>
              <Text>{viewFactor.category || '-'}</Text>
            </div>
            <div>
              <Text strong>说明：</Text>
              <Text>{viewFactor.description || '-'}</Text>
            </div>
            <div>
              <Text strong>代码：</Text>
              <Paragraph
                copyable
                style={{
                  background: '#f6f8fa',
                  padding: 12,
                  borderRadius: 6,
                  maxHeight: 400,
                  overflow: 'auto',
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'monospace',
                }}
              >
                {viewFactor.code}
              </Paragraph>
            </div>
          </Space>
        )}
      </Modal>
    </div>
  );
}
