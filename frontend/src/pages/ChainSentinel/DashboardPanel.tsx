import { useEffect, useMemo, useState } from 'react';
import { Button, Card, Col, Empty, Form, Input, Radio, Row, Space, Tag, message } from 'antd';
import dayjs from 'dayjs';
import { chainSentinelApi } from '../../api/chainSentinel';
import type { SentinelDashboard, SentinelLight } from '../../api/chainSentinel';
import { INDICATORS, LIGHT_MAP } from './constants';

interface DashboardPanelProps {
  dashboard: SentinelDashboard | null;
  onSaved: () => void;
}

interface IndicatorFormValue {
  status?: SentinelLight;
  value_text?: string;
  note?: string;
}

interface DashboardFormValues {
  quarter: string;
  indicators: Record<string, IndicatorFormValue>;
}

export default function DashboardPanel({ dashboard, onSaved }: DashboardPanelProps) {
  const [form] = Form.useForm<DashboardFormValues>();
  const [saving, setSaving] = useState(false);

  // 默认当前季度，如 2026Q3
  const defaultQuarter = useMemo(() => {
    const now = dayjs();
    return `${now.year()}Q${Math.floor(now.month() / 3) + 1}`;
  }, []);

  // 加载时回显：灯态取 current_status，数值描述/备注取当前季度已录入内容
  useEffect(() => {
    if (!dashboard) return;
    const quarter = form.getFieldValue('quarter') || defaultQuarter;
    const indicators: Record<string, IndicatorFormValue> = {};
    for (const ind of INDICATORS) {
      const entry = dashboard.entries.find((e) => e.indicator === ind.code && e.quarter === quarter);
      indicators[ind.code] = {
        status: dashboard.current_status?.[ind.code],
        value_text: entry?.value_text ?? '',
        note: entry?.note ?? '',
      };
    }
    form.setFieldsValue({ indicators });
  }, [dashboard, form, defaultQuarter]);

  // 四个指标逐条提交
  const onFinish = async (values: DashboardFormValues) => {
    setSaving(true);
    try {
      for (const ind of INDICATORS) {
        const v = values.indicators?.[ind.code];
        if (!v?.status) continue;
        await chainSentinelApi.saveDashboardEntry({
          quarter: values.quarter,
          indicator: ind.code,
          status: v.status,
          value_text: v.value_text ?? '',
          note: v.note ?? '',
        });
      }
      message.success('本季指标灯态已保存');
      onSaved();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const latestEntry = (code: string) =>
    dashboard?.entries
      .filter((e) => e.indicator === code)
      .sort((a, b) => (a.updated_at < b.updated_at ? 1 : -1))[0];

  return (
    <Card title="指标层 · 季度灯态录入" style={{ marginBottom: 24 }}>
      <Row gutter={[24, 16]}>
        <Col xs={24} lg={14}>
          <Form form={form} onFinish={onFinish} initialValues={{ quarter: defaultQuarter }}>
            <Form.Item
              name="quarter"
              label="季度"
              rules={[{ required: true, message: '请输入季度' }]}
              style={{ marginBottom: 12 }}
            >
              <Input style={{ width: 140 }} placeholder="如 2026Q3" />
            </Form.Item>
            {INDICATORS.map((ind) => (
              <Card key={ind.code} size="small" title={ind.label} style={{ marginBottom: 12 }}>
                <Space size="middle" wrap>
                  <Form.Item
                    name={['indicators', ind.code, 'status']}
                    label="灯态"
                    rules={[{ required: true, message: '请选择' }]}
                    style={{ marginBottom: 8 }}
                  >
                    <Radio.Group buttonStyle="solid" size="small">
                      <Radio.Button value="green">绿</Radio.Button>
                      <Radio.Button value="yellow">黄</Radio.Button>
                      <Radio.Button value="red">红</Radio.Button>
                    </Radio.Group>
                  </Form.Item>
                  <Form.Item
                    name={['indicators', ind.code, 'value_text']}
                    label="数值描述"
                    style={{ marginBottom: 8 }}
                  >
                    <Input style={{ width: 240 }} placeholder="如 +12% QoQ / 3.5x / MSFT" />
                  </Form.Item>
                  <Form.Item name={['indicators', ind.code, 'note']} label="备注" style={{ marginBottom: 8 }}>
                    <Input style={{ width: 220 }} placeholder="可选" />
                  </Form.Item>
                </Space>
              </Card>
            ))}
            <Button type="primary" htmlType="submit" loading={saving}>
              保存本季灯态
            </Button>
          </Form>
        </Col>
        <Col xs={24} lg={10}>
          <Card size="small" title="各指标当前灯态">
            {dashboard ? (
              INDICATORS.map((ind) => {
                const light = dashboard.current_status?.[ind.code];
                const entry = latestEntry(ind.code);
                return (
                  <div key={ind.code} style={{ marginBottom: 12 }}>
                    <Space size={8}>
                      <span>{ind.label}</span>
                      {light ? (
                        <Tag color={LIGHT_MAP[light].color}>{LIGHT_MAP[light].text}</Tag>
                      ) : (
                        <Tag>未录入</Tag>
                      )}
                    </Space>
                    {entry && (
                      <div style={{ color: '#999', fontSize: 12, marginTop: 2 }}>
                        {entry.quarter}
                        {entry.value_text ? ` · ${entry.value_text}` : ''}
                        {entry.note ? ` · ${entry.note}` : ''} · 更新于{' '}
                        {dayjs(entry.updated_at).format('YYYY-MM-DD HH:mm')}
                      </div>
                    )}
                  </div>
                );
              })
            ) : (
              <Empty description="暂无录入" />
            )}
          </Card>
        </Col>
      </Row>
    </Card>
  );
}
