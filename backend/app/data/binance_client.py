import asyncio
from datetime import datetime
from typing import Any

import aiohttp
import pandas as pd

from app.data.base_client import MarketDataClient
from app.models.enums import Interval, MarketType

SPOT_BASE_URL = "https://api.binance.com"
FUTURES_BASE_URL = "https://fapi.binance.com"

SPOT_KLINES_ENDPOINT = "/api/v3/klines"
FUTURES_KLINES_ENDPOINT = "/fapi/v1/klines"
SPOT_SYMBOLS_ENDPOINT = "/api/v3/exchangeInfo"
FUTURES_SYMBOLS_ENDPOINT = "/fapi/v1/exchangeInfo"

PAGE_SIZE = 1000
REQUEST_INTERVAL = 0.05  # 50ms，Binance 限速 1200 req/min

INTERVAL_TO_MS = {
    "1m": 60_000,
    "5m": 300_000,
    "15m": 900_000,
    "30m": 1_800_000,
    "1h": 3_600_000,
    "4h": 14_400_000,
    "8h": 28_800_000,
    "1d": 86_400_000,
    "7d": 604_800_000,
}


class BinanceClient(MarketDataClient):
    """Binance 公有行情客户端（现货 + U 本位合约）"""

    name = "binance"

    def __init__(self):
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    @staticmethod
    def _normalize_symbol(symbol: str) -> str:
        """将 BTC_USDT 转换为 Binance 格式 BTCUSDT"""
        return symbol.replace("_", "")

    @staticmethod
    def _to_internal_symbol(symbol: str) -> str:
        """将 BTCUSDT 转换回内部格式 BTC_USDT"""
        # 简单处理：从右往左切分出 quote（USDT/BTC/ETH/BUSD/TUSD/FDUSD 等常见稳定币）
        # 实际生产可用交易所 symbol 元数据精确映射
        for quote in ["USDT", "BUSD", "BTC", "ETH", "TUSD", "FDUSD", "USDC", "DAI"]:
            if symbol.endswith(quote):
                base = symbol[: -len(quote)]
                return f"{base}_{quote}"
        # 兜底：如果无法识别，直接返回原值
        return symbol

    def _base_url(self, market_type: MarketType) -> str:
        if market_type == MarketType.SPOT:
            return SPOT_BASE_URL
        return FUTURES_BASE_URL

    def _klines_endpoint(self, market_type: MarketType) -> str:
        if market_type == MarketType.SPOT:
            return SPOT_KLINES_ENDPOINT
        return FUTURES_KLINES_ENDPOINT

    async def _request(self, method: str, url: str, params: dict | None = None) -> Any:
        session = await self._get_session()
        try:
            async with session.request(method, url, params=params) as response:
                if response.status != 200:
                    text = await response.text()
                    raise Exception(
                        f"Binance API 请求失败: {response.status} {response.reason}, "
                        f"url={url}, params={params}, response={text[:200]}"
                    )
                return await response.json()
        except aiohttp.ClientConnectionError as e:
            raise Exception(f"连接 Binance 失败，请检查网络: {type(e).__name__}: {e}") from e
        except aiohttp.ClientError as e:
            raise Exception(f"请求 Binance 异常: {type(e).__name__}: {e}") from e

    async def fetch_klines(
        self,
        symbol: str,
        interval: Interval,
        market_type: MarketType,
        start_time: datetime,
        end_time: datetime,
    ) -> pd.DataFrame:
        """按需拉取 K 线，自动分页"""
        binance_symbol = self._normalize_symbol(symbol)
        interval_ms = INTERVAL_TO_MS.get(interval.value, 3_600_000)

        start_ms = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)

        base_url = self._base_url(market_type)
        endpoint = self._klines_endpoint(market_type)
        url = f"{base_url}{endpoint}"

        all_data: list[list[Any]] = []
        current_from = start_ms
        max_pages = 1000  # 安全上限，足够覆盖 5 年 1h 数据

        for _ in range(max_pages):
            if current_from >= end_ms:
                break

            params = {
                "symbol": binance_symbol,
                "interval": interval.value,
                "startTime": current_from,
                "endTime": end_ms,
                "limit": PAGE_SIZE,
            }

            try:
                batch = await self._request("GET", url, params)
            except Exception as e:
                if "429" in str(e):
                    await asyncio.sleep(1)
                    continue
                raise

            if not batch:
                break

            all_data.extend(batch)

            last_open_time = int(batch[-1][0])
            next_from = last_open_time + interval_ms
            if next_from <= current_from:
                break
            current_from = next_from

            if last_open_time >= end_ms:
                break

            await asyncio.sleep(REQUEST_INTERVAL)

        df = self._normalize_klines(all_data, symbol, interval.value, market_type.value)

        # 过滤到目标时间范围
        start_ts = pd.Timestamp(start_time)
        end_ts = pd.Timestamp(end_time)
        if start_ts.tzinfo is None:
            start_ts = start_ts.tz_localize("UTC")
        if end_ts.tzinfo is None:
            end_ts = end_ts.tz_localize("UTC")
        df = df[(df["timestamp"] >= start_ts) & (df["timestamp"] <= end_ts)]
        return df.reset_index(drop=True)

    def _normalize_klines(
        self,
        raw_data: list[list[Any]],
        symbol: str,
        interval: str,
        market_type: str,
    ) -> pd.DataFrame:
        """将 Binance K 线数组标准化为统一 OHLCV DataFrame"""
        if not raw_data:
            return pd.DataFrame(
                columns=[
                    "timestamp",
                    "open",
                    "high",
                    "low",
                    "close",
                    "volume",
                    "market_type",
                    "symbol",
                    "interval",
                ]
            )

        # Binance 返回: [open_time, open, high, low, close, volume, close_time, quote_volume, ...]
        trimmed = [row[:6] for row in raw_data]
        df = pd.DataFrame(trimmed, columns=["timestamp", "open", "high", "low", "close", "volume"])

        # Binance 时间戳为毫秒
        df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df = df.sort_values("timestamp").reset_index(drop=True)

        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        df["market_type"] = market_type
        df["symbol"] = symbol
        df["interval"] = interval

        return df[["timestamp", "open", "high", "low", "close", "volume", "market_type", "symbol", "interval"]]

    async def get_spot_symbols(self) -> list[dict[str, Any]]:
        """获取现货交易对列表"""
        url = f"{SPOT_BASE_URL}{SPOT_SYMBOLS_ENDPOINT}"
        data = await self._request("GET", url)
        symbols = []
        for item in data.get("symbols", []):
            if item.get("status") != "TRADING":
                continue
            symbol = item.get("symbol", "")
            base = item.get("baseAsset", "")
            quote = item.get("quoteAsset", "")
            symbols.append({
                "symbol": self._to_internal_symbol(symbol),
                "market_type": MarketType.SPOT.value,
                "base": base,
                "quote": quote,
            })
        return symbols

    async def get_futures_symbols(self, settle: str = "usdt") -> list[dict[str, Any]]:
        """获取 U 本位合约交易对列表"""
        if settle != "usdt":
            # Binance 公有接口主要提供 USDT 本位与 USD 本位；这里仅支持 USDT 本位
            return []

        url = f"{FUTURES_BASE_URL}{FUTURES_SYMBOLS_ENDPOINT}"
        data = await self._request("GET", url)
        symbols = []
        for item in data.get("symbols", []):
            if item.get("status") != "TRADING":
                continue
            symbol = item.get("symbol", "")
            base = item.get("baseAsset", "")
            quote = item.get("quoteAsset", "")
            symbols.append({
                "symbol": self._to_internal_symbol(symbol),
                "market_type": MarketType.FUTURES_USDT.value,
                "base": base,
                "quote": quote,
            })
        return symbols
