import { useEffect, useState } from 'react';
import { Button, Card, Col, Empty, Row, Spin, message } from 'antd';
import { chainSentinelApi } from '../../api/chainSentinel';
import type {
  SentinelDashboard,
  SentinelEvent,
  SentinelHistoryItem,
  SentinelMember,
  SentinelNewsItem,
  SentinelStatus,
} from '../../api/chainSentinel';
import DashboardPanel from './DashboardPanel';
import HistoryChart from './HistoryChart';
import LightCard from './LightCard';
import NewsPanel from './NewsPanel';
import PricePanel from './PricePanel';

export default function ChainSentinel() {
  const [status, setStatus] = useState<SentinelStatus | null>(null);
  const [history, setHistory] = useState<SentinelHistoryItem[]>([]);
  const [news, setNews] = useState<SentinelNewsItem[]>([]);
  const [dashboard, setDashboard] = useState<SentinelDashboard | null>(null);
  const [events, setEvents] = useState<SentinelEvent[]>([]);
  // 成员明细只在 POST /scan 响应里返回（GET /status 没有），由页面级 state 持有
  const [members, setMembers] = useState<SentinelMember[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [scanning, setScanning] = useState(false);

  const loadAll = async () => {
    const [statusRes, historyRes, newsRes, dashboardRes, eventsRes] = await Promise.all([
      chainSentinelApi.getStatus().catch(() => {
        message.error('获取哨兵状态失败');
        return null;
      }),
      chainSentinelApi.getHistory(90).catch(() => {
        message.error('获取历史评分失败');
        return [] as SentinelHistoryItem[];
      }),
      chainSentinelApi.getNews(7).catch(() => {
        message.error('获取命中新闻失败');
        return [] as SentinelNewsItem[];
      }),
      chainSentinelApi.getDashboard().catch(() => {
        message.error('获取指标灯态失败');
        return null;
      }),
      chainSentinelApi.getEvents(50).catch(() => {
        message.error('获取灯色事件失败');
        return [] as SentinelEvent[];
      }),
    ]);
    setStatus(statusRes);
    setHistory(historyRes);
    setNews(newsRes);
    setDashboard(dashboardRes);
    setEvents(eventsRes);
  };

  useEffect(() => {
    setLoading(true);
    loadAll().finally(() => setLoading(false));
  }, []);

  const handleScan = async () => {
    setScanning(true);
    try {
      const result = await chainSentinelApi.scan();
      setMembers(result.members);
      message.success(`扫描完成：命中新闻 ${result.news_hits} 条${result.notified ? '，灯色变化已推送' : ''}`);
      await loadAll();
    } catch (err: any) {
      message.error(err?.response?.data?.detail || '扫描失败');
    } finally {
      setScanning(false);
    }
  };

  if (loading) {
    return (
      <div style={{ padding: 100, textAlign: 'center' }}>
        <Spin size="large" />
      </div>
    );
  }

  const ready = status && status.ready ? status : null;

  return (
    <div style={{ padding: 24 }}>
      <h1>链风险哨兵</h1>
      <p style={{ color: '#666' }}>
        监控 OpenAI 算力产业链「良性循环 → 循环破裂」的逃顶风险：价格层（成员股相对强弱）+ 新闻层（负面关键词命中）+
        指标层（capex / 融资 / backlog 季度灯态）三层合成综合评分，输出绿（正常）/ 黄（警惕）/ 红（逃顶信号）三档灯色。
      </p>

      {ready ? (
        <LightCard status={ready} scanning={scanning} onScan={handleScan} />
      ) : (
        <Card style={{ marginBottom: 24 }}>
          <Empty description={status && 'message' in status && status.message ? status.message : '尚未扫描，点击立即扫描'}>
            <Button type="primary" loading={scanning} onClick={handleScan}>
              立即扫描
            </Button>
            <div style={{ marginTop: 8, color: '#999', fontSize: 12 }}>
              首次扫描需拉取行情与新闻数据，耗时数十秒
            </div>
          </Empty>
        </Card>
      )}

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col xs={24} lg={12}>
          <PricePanel members={members} history={history} />
        </Col>
        <Col xs={24} lg={12}>
          <NewsPanel news={news} />
        </Col>
      </Row>

      <DashboardPanel dashboard={dashboard} onSaved={loadAll} />

      <HistoryChart history={history} events={events} />
    </div>
  );
}
