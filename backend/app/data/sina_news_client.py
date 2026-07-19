"""
新浪财经 7×24 快讯客户端（免费，无需 API key）

- 接口：https://zhibo.sina.com.cn/api/zhibo/feed（zhibo_id=152 财经快讯）
- 滚动时间线，无 ticker 查询：按页拉取近期快讯后本地关键词过滤
- 每次扫描拉取最近窗口（默认 7 天、最多 5 页 × 100 条），每日一次，不轮询
- 选它的原因：本机无法访问 Google News RSS，Tiingo 免费 key 无 News API 权限，
  新浪 7×24 覆盖美股/AI 产业链重大新闻且无需认证

输出与 TiingoNewsClient 统一的字段：id / title / url / source / published_at / tickers / description
"""

import asyncio
import html
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any

import aiohttp

FEED_URL = "https://zhibo.sina.com.cn/api/zhibo/feed"
ZHIBO_ID = 152
PAGE_SIZE = 100
MAX_PAGES = 5
CN_TZ = timezone(timedelta(hours=8))

# 链成员代码 -> 文本别名（小写/中文），用于给快讯打 ticker 标记
TICKER_ALIASES = {
    "NVDA": ["nvda", "nvidia", "英伟达"],
    "AMD": ["amd"],
    "AVGO": ["avgo", "broadcom", "博通"],
    "ORCL": ["orcl", "oracle", "甲骨文"],
    "MSFT": ["msft", "microsoft", "微软"],
    "AMZN": ["amzn", "amazon", "亚马逊"],
    "CRWV": ["crwv", "coreweave"],
    "SFTBY": ["sftby", "softbank", "软银"],
}

_TAG_RE = re.compile(r"<[^>]+>")


def detect_tickers(text: str) -> list[str]:
    """按别名在快讯文本中识别链成员 ticker"""
    low = text.lower()
    return [sym for sym, aliases in TICKER_ALIASES.items() if any(a in low for a in aliases)]


def parse_feed(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """解析新浪快讯响应为统一文章列表（纯函数，可单测）"""
    items = (payload.get("result", {}).get("data", {}).get("feed", {}) or {}).get("list", [])
    articles = []
    for it in items:
        text = html.unescape(_TAG_RE.sub("", it.get("rich_text", ""))).strip()
        if not text:
            continue
        ts = it.get("create_time", "")
        try:
            published = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CN_TZ)
            published_at = published.isoformat()
        except ValueError:
            published_at = ""
        articles.append({
            "id": str(it.get("id", "")),
            "title": text[:60] + ("…" if len(text) > 60 else ""),
            "url": it.get("docurl", "") or "",
            "source": "新浪财经7x24",
            "published_at": published_at,
            "tickers": detect_tickers(text),
            "description": text,
        })
    return articles


class SinaNewsClient:
    """新浪 7×24 快讯客户端：拉取近 N 天快讯"""

    def __init__(self):
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": "Mozilla/5.0"})
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
        self._session = None

    async def fetch_news(
        self,
        tickers: list[str] | None = None,  # 接口对齐用；新浪无 ticker 查询，本地过滤
        days: int = 7,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """拉取近 days 天的快讯（分页直至超出窗口或达到页数上限）"""
        cutoff = datetime.now(CN_TZ) - timedelta(days=days)
        session = await self._get_session()

        articles: list[dict[str, Any]] = []
        for page in range(1, MAX_PAGES + 1):
            async with session.get(
                FEED_URL,
                params={"page": str(page), "page_size": str(PAGE_SIZE), "zhibo_id": str(ZHIBO_ID)},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status != 200:
                    raise Exception(f"新浪快讯请求失败: HTTP {response.status}")
                payload = json.loads(await response.text())

            batch = parse_feed(payload)
            if not batch:
                break
            articles.extend(batch)

            # 本页最旧一条已超出窗口 → 停止翻页
            oldest = min(
                (a["published_at"] for a in batch if a["published_at"]), default=None)
            if oldest is None or datetime.fromisoformat(oldest) < cutoff:
                break
            await asyncio.sleep(0.3)  # 克制请求频率

        # 只保留窗口内
        articles = [
            a for a in articles
            if a["published_at"] and datetime.fromisoformat(a["published_at"]) >= cutoff
        ]
        return articles[:limit]
