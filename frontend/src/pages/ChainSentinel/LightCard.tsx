import { Alert, Button, Card, Col, Row, Space, Statistic, Tag } from 'antd';
import dayjs from 'dayjs';
import type { SentinelStatusReady } from '../../api/chainSentinel';
import { LIGHT_MAP, REGIME_MAP } from './constants';

interface LightCardProps {
  status: SentinelStatusReady;
  scanning: boolean;
  onScan: () => void;
}

export default function LightCard({ status, scanning, onScan }: LightCardProps) {
  const light = LIGHT_MAP[status.light];
  const regime = REGIME_MAP[status.regime];
  const { reasons } = status;

  const reasonGroups = [
    { title: '判级理由', items: reasons.light },
    { title: '价格层', items: reasons.price },
    { title: '新闻层', items: reasons.news },
    { title: '指标层', items: reasons.dashboard },
  ].filter((g) => g.items.length > 0);

  return (
    <Card style={{ marginBottom: 24, background: light.bg, borderColor: light.border }}>
      <Row gutter={[24, 16]} align="middle">
        <Col flex="none" style={{ textAlign: 'center' }}>
          <div
            style={{
              width: 72,
              height: 72,
              borderRadius: '50%',
              background: light.color,
              boxShadow: `0 0 18px ${light.color}`,
              margin: '0 auto 8px',
            }}
          />
          <div style={{ fontSize: 20, fontWeight: 'bold', color: light.color }}>{light.text}</div>
        </Col>
        <Col flex="auto">
          <Space size="large" wrap align="start">
            <Statistic title="综合评分" value={status.total_score} />
            <Statistic title="价格层" value={status.price_score} />
            <Statistic title="新闻层" value={status.news_score} />
            <Statistic title="指标层" value={status.dash_score} />
            <div>
              <div style={{ color: '#666', marginBottom: 4 }}>情景判级</div>
              <Tag color={regime.color} style={{ fontSize: 14, padding: '2px 10px' }}>
                {regime.text}
              </Tag>
            </div>
            <Statistic title="数据日期" value={status.date} />
          </Space>
          <div style={{ color: '#999', fontSize: 12, marginTop: 4 }}>
            生成时间：{dayjs(status.created_at).format('YYYY-MM-DD HH:mm')}
          </div>
          {reasonGroups.map((g) => (
            <div key={g.title} style={{ marginTop: 8 }}>
              <span style={{ fontWeight: 600 }}>{g.title}</span>
              <ul style={{ margin: '4px 0 0', paddingLeft: 20 }}>
                {g.items.map((r, i) => (
                  <li key={i}>{r}</li>
                ))}
              </ul>
            </div>
          ))}
          {reasons.news_error && (
            <Alert style={{ marginTop: 8 }} type="warning" showIcon message={`新闻层数据异常：${reasons.news_error}`} />
          )}
        </Col>
        <Col flex="160px" style={{ textAlign: 'center' }}>
          <Button type="primary" size="large" loading={scanning} onClick={onScan} block>
            立即扫描
          </Button>
          <div style={{ marginTop: 8, color: '#999', fontSize: 12 }}>全量扫描需数十秒，请耐心等待</div>
        </Col>
      </Row>
    </Card>
  );
}
