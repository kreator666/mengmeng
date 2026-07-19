"""
Tiingo 财经新闻客户端（免费方案）

- 接口：GET https://api.tiingo.com/tiingo/news
- 配额约束：免费档按天限额，设计上每日扫描只拉一次（近 N 天、链成员 ticker），
  本地 SQLite 按文章 id 去重，不做轮询
- API key：复用美股行情的配置（环境变量 TIINGO_API_KEY 或
  backend/data/us_stock_config.json 的 tiingo_api_key 字段）
"""

import os
from datetime import datetime, timedelta
from typing import Any

import aiohttp

from app.data.us_stock_client import _load_key_from_config

NEWS_URL = "https://api.tiingo.com/tiingo/news"


class TiingoNewsClient:
    """Tiingo 新闻客户端：按 ticker 拉取近期新闻"""

    def __init__(self, api_key: str | None = None):
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = os.environ.get("TIINGO_API_KEY", "") or _load_key_from_config()
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def fetch_news(
        self,
        tickers: list[str],
        days: int = 7,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        拉取 tickers 相关新闻（近 days 天）

        返回统一字段：id / title / url / source / published_at / tickers / description
        """
        if not self.api_key:
            raise Exception(
                "未配置 Tiingo API key。请设置环境变量 TIINGO_API_KEY，或写入 "
                "backend/data/us_stock_config.json 的 tiingo_api_key 字段"
            )

        end = datetime.utcnow()
        start = end - timedelta(days=days)
        params = {
            "tickers": ",".join(t.lower() for t in tickers),
            "startDate": start.strftime("%Y-%m-%d"),
            "endDate": end.strftime("%Y-%m-%d"),
            "limit": str(limit),
            "token": self.api_key,
        }

        session = await self._get_session()
        async with session.get(
            NEWS_URL, params=params, timeout=aiohttp.ClientTimeout(total=60)
        ) as response:
            if response.status in (401, 403):
                raise Exception(
                    "Tiingo 免费 key 无 News API 权限；"
                    "请在 backend/data/sentinel_config.json 将 news.provider 改为 sina")
            if response.status == 429:
                raise Exception("Tiingo 新闻请求超出限速，请稍后重试")
            if response.status != 200:
                raise Exception(f"Tiingo 新闻请求失败: HTTP {response.status}")
            payload = await response.json(content_type=None)

        articles = []
        for item in payload or []:
            articles.append({
                "id": str(item.get("id", "")),
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "published_at": item.get("publishedDate", ""),
                "tickers": [t.upper() for t in item.get("tickers", []) or []],
                "description": item.get("description", "") or "",
            })
        return articles
