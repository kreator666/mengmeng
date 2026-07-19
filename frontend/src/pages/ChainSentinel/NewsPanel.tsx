import { Card, List, Space, Tag } from 'antd';
import dayjs from 'dayjs';
import type { SentinelNewsItem } from '../../api/chainSentinel';

interface NewsPanelProps {
  news: SentinelNewsItem[];
}

export default function NewsPanel({ news }: NewsPanelProps) {
  return (
    <Card title="新闻层 · 近 7 日命中" style={{ height: '100%' }}>
      <List
        dataSource={news}
        locale={{ emptyText: '近期无命中负面新闻' }}
        pagination={{ pageSize: 8, hideOnSinglePage: true }}
        renderItem={(item) => (
          <List.Item>
            <div style={{ width: '100%' }}>
              <Space size={8} wrap>
                {item.heavy && <Tag color="red">重磅</Tag>}
                <a href={item.url} target="_blank" rel="noreferrer">
                  {item.title}
                </a>
              </Space>
              <div style={{ marginTop: 4 }}>
                <Space size={8} wrap>
                  <span style={{ color: '#999' }}>{item.source}</span>
                  <span style={{ color: '#999' }}>{dayjs(item.published_at).format('YYYY-MM-DD HH:mm')}</span>
                  {item.matched_keywords.map((k) => (
                    <Tag key={k} color="orange">
                      {k}
                    </Tag>
                  ))}
                  {item.tickers.map((t) => (
                    <Tag key={t}>{t}</Tag>
                  ))}
                </Space>
              </div>
            </div>
          </List.Item>
        )}
      />
    </Card>
  );
}
