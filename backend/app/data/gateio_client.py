import asyncio
from datetime import datetime, timedelta
from typing import Any

import aiohttp
import pandas as pd

from app.models.enums import Interval, MarketType
from app.utils.helpers import normalize_ohlcv, to_unix_timestamp

BASE_URL = "https://api.gateio.ws/api/v4"
SPOT_KLINES_ENDPOINT = "/spot/candlesticks"
FUTURES_KLINES_ENDPOINT = "/futures/{settle}/candlesticks"

SPOT_PAGE_SIZE = 1000
FUTURES_PAGE_SIZE = 2000
REQUEST_INTERVAL = 0.2  # 200ms

COLUMN_ORDER = ["timestamp", "volume", "close", "high", "low", "open"]

# 各周期对应的秒数
INTERVAL_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "4h": 14400,
    "8h": 28800,
    "1d": 86400,
    "7d": 604800,
}


class GateIOClient:
    """Gate.io API v4 客户端"""

    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def _request(self, method: str, path: str, params: dict | None = None) -> Any:
        session = await self._get_session()
        url = f"{self.base_url}{path}"
        async with session.request(method, url, params=params) as response:
            response.raise_for_status()
            return await response.json()

    async def fetch_klines(
        self,
        symbol: str,
        interval: Interval,
        market_type: MarketType,
        start_time: datetime,
        end_time: datetime,
    ) -> pd.DataFrame:
        """
        按需拉取 K 线数据，自动处理分页
        使用 from + limit 方式分页，避免 from/to 互斥问题
        """
        from_ts = to_unix_timestamp(start_time)
        to_ts = to_unix_timestamp(end_time)

        if market_type == MarketType.SPOT:
            page_size = SPOT_PAGE_SIZE
            endpoint = SPOT_KLINES_ENDPOINT
            params_key = "currency_pair"
        else:
            page_size = FUTURES_PAGE_SIZE
            settle = "usdt" if market_type == MarketType.FUTURES_USDT else "btc"
            endpoint = FUTURES_KLINES_ENDPOINT.format(settle=settle)
            params_key = "contract"

        interval_sec = INTERVAL_SECONDS.get(interval.value, 3600)
        all_data: list[list[Any]] = []
        current_from = from_ts
        max_pages = 100  # 安全上限

        for _ in range(max_pages):
            if current_from >= to_ts:
                break

            params = {
                params_key: symbol,
                "interval": interval.value,
                "from": current_from,
                "limit": page_size,
            }

            try:
                batch = await self._request("GET", endpoint, params)
            except aiohttp.ClientResponseError as e:
                if e.status == 429:
                    await asyncio.sleep(1)
                    continue
                raise

            if not batch:
                break

            all_data.extend(batch)

            # 计算下一页起点
            last_ts = int(batch[-1][0])
            next_from = last_ts + interval_sec
            if next_from <= current_from:
                break
            current_from = next_from

            # 如果已获取到目标时间之后，提前结束
            if last_ts >= to_ts:
                break

            await asyncio.sleep(REQUEST_INTERVAL)

        df = normalize_ohlcv(all_data, market_type.value, symbol, interval.value, COLUMN_ORDER)

        # 过滤到目标时间范围
        start_ts = pd.Timestamp(start_time)
        end_ts = pd.Timestamp(end_time)
        if start_ts.tzinfo is None:
            start_ts = start_ts.tz_localize("UTC")
        if end_ts.tzinfo is None:
            end_ts = end_ts.tz_localize("UTC")
        df = df[(df["timestamp"] >= start_ts) & (df["timestamp"] <= end_ts)]
        return df.reset_index(drop=True)

    async def get_spot_symbols(self) -> list[dict[str, Any]]:
        """获取现货交易对列表"""
        return await self._request("GET", "/spot/currency_pairs")

    async def get_futures_contracts(self, settle: str = "usdt") -> list[dict[str, Any]]:
        """获取合约交易对列表"""
        return await self._request("GET", f"/futures/{settle}/contracts")
