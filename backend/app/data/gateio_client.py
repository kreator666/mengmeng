import asyncio
from datetime import datetime
from typing import Any

import aiohttp
import pandas as pd

from app.data.base_client import MarketDataClient
from app.models.enums import Interval, MarketType
from app.utils.helpers import normalize_ohlcv, to_unix_timestamp

BASE_URL = "https://api.gateio.ws/api/v4"
SPOT_KLINES_ENDPOINT = "/spot/candlesticks"
FUTURES_KLINES_ENDPOINT = "/futures/{settle}/candlesticks"

SPOT_PAGE_SIZE = 1000
FUTURES_PAGE_SIZE = 2000
REQUEST_INTERVAL = 0.2  # 200ms

COLUMN_ORDER = ["timestamp", "volume", "close", "high", "low", "open"]


def _tick_to_decimals(tick: Any) -> int:
    """将 tick 字符串（如 '0.0000001'、'0.05'）转换为小数位数"""
    if not tick:
        return 4
    s = str(tick)
    if "." in s:
        return len(s.rstrip("0").split(".")[1])
    return 0

# 各周期对应的秒数
INTERVAL_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1h": 3600,
    "2h": 7200,
    "4h": 14400,
    "8h": 28800,
    "1d": 86400,
    "3d": 259200,
    "7d": 604800,
    "30d": 2592000,
}


def resample_to_quarter(df: pd.DataFrame) -> pd.DataFrame:
    """将 30d K 线聚合为季线（3M），K 线时间戳取季度起始日"""
    if df.empty:
        return df
    quarterly = (
        df.set_index("timestamp")
        .resample("QS")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
        .reset_index()
    )
    quarterly["market_type"] = df["market_type"].iloc[0]
    quarterly["symbol"] = df["symbol"].iloc[0]
    quarterly["interval"] = "3M"
    return quarterly


class GateIOClient(MarketDataClient):
    """Gate.io API v4 客户端"""

    name = "gateio"

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
        try:
            async with session.request(method, url, params=params) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(
                        f"Gate.io API 请求失败: {response.status} {response.reason}, "
                        f"url={url}, params={params}, response={text[:200]}"
                    )
                return await response.json()
        except aiohttp.ClientConnectionError as e:
            raise Exception(f"连接 Gate.io 失败，请检查网络: {type(e).__name__}: {e}") from e
        except aiohttp.ClientError as e:
            raise Exception(f"请求 Gate.io 异常: {type(e).__name__}: {e}") from e

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

        - 现货：使用 from + limit 分页
        - 合约：Gate.io 合约接口中 limit 与 from/to 互斥，使用 from + to 分页
        """
        from_ts = to_unix_timestamp(start_time)
        to_ts = to_unix_timestamp(end_time)

        # 季线（3M）：Gate.io 无此周期，拉取月线（30d）后聚合
        if interval == Interval.THREE_MONTHS:
            monthly = await self.fetch_klines(
                symbol, Interval.ONE_MONTH, market_type, start_time, end_time
            )
            return resample_to_quarter(monthly)

        if market_type == MarketType.SPOT:
            page_size = SPOT_PAGE_SIZE
            endpoint = SPOT_KLINES_ENDPOINT
            params_key = "currency_pair"
            use_limit = True
        else:
            page_size = FUTURES_PAGE_SIZE
            settle = "usdt" if market_type == MarketType.FUTURES_USDT else "btc"
            endpoint = FUTURES_KLINES_ENDPOINT.format(settle=settle)
            params_key = "contract"
            use_limit = False

        interval_sec = INTERVAL_SECONDS.get(interval.value, 3600)
        all_data: list[list[Any]] = []
        current_from = from_ts
        max_pages = 100  # 安全上限

        for _ in range(max_pages):
            if current_from >= to_ts:
                break

            if use_limit:
                params = {
                    params_key: symbol,
                    "interval": interval.value,
                    "from": current_from,
                    "limit": page_size,
                }
            else:
                # 合约：按 page_size 切分时间窗口
                page_to = min(current_from + page_size * interval_sec, to_ts)
                params = {
                    params_key: symbol,
                    "interval": interval.value,
                    "from": current_from,
                    "to": page_to,
                }

            try:
                batch = await self._request("GET", endpoint, params)
            except Exception as e:
                if "429" in str(e):
                    await asyncio.sleep(1)
                    continue
                raise

            if not batch:
                break

            # 统一格式：现货返回列表，合约返回字典列表
            normalized_batch = self._normalize_kline_batch(batch, market_type)
            all_data.extend(normalized_batch)

            # 计算下一页起点
            last_ts = int(normalized_batch[-1][0])
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

    def _normalize_kline_batch(
        self, batch: list[Any], market_type: MarketType
    ) -> list[list[Any]]:
        """
        将 Gate.io 不同接口返回的 K 线数据统一为 [timestamp, volume, close, high, low, open] 列表
        """
        if not batch:
            return []

        # 现货返回的是列表：[[t, v, c, h, l, o], ...]
        if market_type == MarketType.SPOT:
            return batch

        # 合约返回的是字典列表：[{"t": ..., "v": ..., "c": ..., "h": ..., "l": ..., "o": ...}, ...]
        normalized = []
        for item in batch:
            if isinstance(item, dict):
                normalized.append([
                    item.get("t"),
                    item.get("v"),
                    item.get("c"),
                    item.get("h"),
                    item.get("l"),
                    item.get("o"),
                ])
        return normalized

    async def get_spot_symbols(self) -> list[dict[str, Any]]:
        """获取现货交易对列表"""
        raw = await self._request("GET", "/spot/currency_pairs")
        return [
            {
                "symbol": item.get("id"),
                "market_type": MarketType.SPOT.value,
                "base": item.get("base"),
                "quote": item.get("quote"),
                "price_precision": int(item.get("precision") or 4),
            }
            for item in raw
            if item.get("trade_status") == "tradable"
        ]

    async def get_futures_symbols(self, settle: str = "usdt") -> list[dict[str, Any]]:
        """获取合约交易对列表"""
        raw = await self._request("GET", f"/futures/{settle}/contracts")
        market_type = (
            MarketType.FUTURES_USDT if settle == "usdt" else MarketType.FUTURES_BTC
        )
        return [
            {
                "symbol": item.get("name"),
                "market_type": market_type.value,
                "base": item.get("base"),
                "quote": item.get("quote"),
                "price_precision": _tick_to_decimals(item.get("order_price_round")),
            }
            for item in raw
        ]
