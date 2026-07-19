"""
美股行情客户端（Tiingo 免费方案）

- 数据：/tiingo/daily/{ticker}/prices，一次返回全历史，
  响应自带 adjOpen/adjHigh/adjLow/adjClose（拆股+分红复权，与 TradingView 口径一致）
- 周期：日线原生；周线/月线/季线由日线本地聚合
  （免费档 1000 次/天、500 个品种，历史走本地缓存）
- API key 配置（按优先级）：
  1. 环境变量 TIINGO_API_KEY
  2. 配置文件 backend/data/us_stock_config.json 的 tiingo_api_key 字段
  （免费申请 https://api.tiingo.com → Sign up → Account 页面可见 API token）
"""

import asyncio
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import aiohttp
import pandas as pd

from app.data.base_client import MarketDataClient
from app.models.enums import Interval, MarketType

CONFIG_FILE = Path(__file__).resolve().parents[2] / "data" / "us_stock_config.json"

# 全历史本地存储目录（parquet，每品种一份，增量更新）
HISTORY_DIR = Path(__file__).resolve().parents[2] / "data" / "cache" / "us_stock_history"

# 历史起点（Tiingo 对早于上市日期自动从上市日开始）
HISTORY_START = "2000-01-01"


def _load_key_from_config() -> str:
    """从 backend/data/us_stock_config.json 读取 API key"""
    try:
        if CONFIG_FILE.is_file():
            with open(CONFIG_FILE, encoding="utf-8") as f:
                cfg = json.load(f)
            return cfg.get("tiingo_api_key", "")
    except Exception:
        pass
    return ""


# 周期 -> pandas resample 规则（日线无需聚合）
INTERVAL_RESAMPLE = {
    "7d": "W",   # 周线
    "30d": "MS",  # 月线（月初标记）
    "3M": "QS",   # 季线（季初标记）
}

# 热门美股/ETF 预设列表（界面上也可手动输入任意 ticker）
POPULAR_US_STOCKS = [
    "SOXL", "SOXS", "TQQQ", "SQQQ", "QLD", "SPXL", "SPXS", "FNGU", "NVDL",
    "LABU", "LABD", "UVXY", "NVDA", "TSLA", "AAPL", "AMD", "MSFT", "AMZN",
    "GOOGL", "META", "AVGO", "MSTR", "COIN", "PLTR", "QQQ", "SPY", "IWM",
    "DIA", "GLD", "TLT",
]


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """将 K 线聚合为大周期（时间戳取周期起始，周线标签对齐到周一避免当前周丢失）"""
    if df.empty:
        return df
    out = (
        df.set_index("timestamp")
        .resample(rule, label="left", closed="left")
        .agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
        .dropna()
        .reset_index()
    )
    out["market_type"] = df["market_type"].iloc[0]
    out["symbol"] = df["symbol"].iloc[0]
    return out


class USStockClient(MarketDataClient):
    """Tiingo 美股数据客户端"""

    name = "us_stock"

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

    @staticmethod
    def _require_key(api_key: str):
        if not api_key:
            raise Exception(
                "未配置 Tiingo API key。请免费申请 https://api.tiingo.com "
                "并设置环境变量 TIINGO_API_KEY，或写入 "
                "backend/data/us_stock_config.json 的 tiingo_api_key 字段"
            )

    @staticmethod
    def _parse_prices(payload: list, symbol: str) -> pd.DataFrame:
        """解析 Tiingo 日线响应（使用复权列）为统一 OHLCV DataFrame"""
        rows = []
        for bar in payload:
            rows.append({
                "timestamp": pd.Timestamp(bar["date"]).tz_convert("UTC"),
                "open": float(bar["adjOpen"]),
                "high": float(bar["adjHigh"]),
                "low": float(bar["adjLow"]),
                "close": float(bar["adjClose"]),
                "volume": float(bar["adjVolume"]),
            })
        df = pd.DataFrame(rows)
        if df.empty:
            return pd.DataFrame(
                columns=["timestamp", "open", "high", "low", "close", "volume", "market_type", "symbol", "interval"]
            )
        df = df.sort_values("timestamp").reset_index(drop=True)
        df["market_type"] = MarketType.SPOT.value
        df["symbol"] = symbol
        df["interval"] = "1d"
        return df[["timestamp", "open", "high", "low", "close", "volume", "market_type", "symbol", "interval"]]

    async def _fetch_range(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """拉取 [start, end] 区间的日线（小响应，带重试）"""
        url = f"https://api.tiingo.com/tiingo/daily/{symbol}/prices"
        session = await self._get_session()
        last_err: Exception | None = None
        for _ in range(3):
            try:
                async with session.get(
                    url,
                    params={"startDate": start, "endDate": end, "token": self.api_key},
                    timeout=aiohttp.ClientTimeout(total=120),
                ) as response:
                    if response.status in (401, 403):
                        raise Exception("Tiingo API key 无效，请检查配置")
                    if response.status == 404:
                        raise Exception(f"美股代码无效: {symbol}")
                    if response.status == 429:
                        raise Exception("Tiingo 请求超出限速，请稍后重试")
                    if response.status != 200:
                        raise Exception(f"Tiingo 请求失败: HTTP {response.status}")
                    payload = await response.json(content_type=None)
                    return self._parse_prices(payload, symbol)
            except asyncio.TimeoutError as e:
                last_err = e
            except aiohttp.ClientError as e:
                last_err = Exception(f"连接 Tiingo 失败: {type(e).__name__}: {e}")
        if isinstance(last_err, asyncio.TimeoutError):
            raise Exception(f"Tiingo 请求超时（{symbol} {start}~{end}），请重试")
        raise last_err or Exception("Tiingo 请求失败")

    async def _fetch_chunked(self, symbol: str, start: pd.Timestamp, end: pd.Timestamp) -> pd.DataFrame:
        """分片拉取 [start, end] 区间日线：6 个月一片 + 并发 4 路，失败片串行重试一次

        规避大响应被限速；免费档有小时/每日配额，分片数克制在每月约 2 次请求
        """
        periods = pd.period_range(start, end, freq="6M")
        semaphore = asyncio.Semaphore(4)

        async def one(period) -> tuple[pd.DataFrame, str | None]:
            async with semaphore:
                s = period.start_time.strftime("%Y-%m-%d")
                e = min(period.end_time, end).strftime("%Y-%m-%d")
                try:
                    return await self._fetch_range(symbol, s, e), None
                except Exception as exc:
                    return pd.DataFrame(), f"{s}~{e}: {exc}"

        parts, failures = [], []
        results = await asyncio.gather(*[one(p) for p in periods])
        for df, err in results:
            if df is not None and not df.empty:
                parts.append(df)
            if err:
                failures.append(err)

        # 失败分片串行重试一次（配额类错误立刻放弃，不浪费请求）
        if failures:
            if any("配额" in f or "429" in f or "限速" in f for f in failures):
                raise Exception("Tiingo 请求配额已用尽（免费档有小时/每日上限），请稍后再试")
            retry = []
            for f in failures:
                rng = f.split(":")[0]
                s, e = rng.split("~")
                try:
                    df = await self._fetch_range(symbol, s, e)
                    if not df.empty:
                        retry.append(df)
                except Exception as exc:
                    raise Exception(f"Tiingo 分片拉取失败（{rng}）: {exc}")
            parts.extend(retry)

        if not parts:
            raise Exception(f"Tiingo 未能获取 {symbol} 任何历史数据")
        df = pd.concat(parts, ignore_index=True)
        df = df.drop_duplicates(subset=["timestamp"], keep="last").sort_values("timestamp").reset_index(drop=True)
        df["interval"] = "1d"
        return df

    @staticmethod
    def _read_store(symbol: str) -> pd.DataFrame | None:
        file = HISTORY_DIR / f"{symbol}.parquet"
        if not file.is_file():
            return None
        try:
            return pd.read_parquet(file)
        except Exception:
            return None

    @staticmethod
    def _write_store(symbol: str, df: pd.DataFrame):
        HISTORY_DIR.mkdir(parents=True, exist_ok=True)
        df.to_parquet(HISTORY_DIR / f"{symbol}.parquet", index=False)

    async def _fetch_daily(self, symbol: str) -> pd.DataFrame:
        """获取全历史复权日线：本地存储优先，只做增量更新（大缺口走分片）"""
        local = self._read_store(symbol)
        today = pd.Timestamp.utcnow().tz_localize(None).normalize()

        if local is not None and not local.empty:
            last_date = local["timestamp"].max().tz_localize(None).normalize()
            gap_days = (today - last_date).days
            # 数据覆盖到最近一个自然日即视为新鲜（周末/节假日不重复拉）
            if gap_days <= 1:
                return local
            missing_start = last_date + pd.Timedelta(days=1)
            if gap_days <= 60:
                new = await self._fetch_range(
                    symbol, missing_start.strftime("%Y-%m-%d"), today.strftime("%Y-%m-%d")
                )
            else:
                new = await self._fetch_chunked(symbol, missing_start, today)
            if not new.empty:
                local = pd.concat([local, new], ignore_index=True)
                local = local.drop_duplicates(subset=["timestamp"], keep="last").sort_values("timestamp").reset_index(drop=True)
                self._write_store(symbol, local)
            return local

        # 首次：取元数据拿上市日期，再分片拉全历史
        start = pd.Timestamp(HISTORY_START)
        try:
            session = await self._get_session()
            async with session.get(
                f"https://api.tiingo.com/tiingo/daily/{symbol}",
                params={"token": self.api_key},
                timeout=aiohttp.ClientTimeout(total=30),
            ) as response:
                if response.status == 200:
                    meta = await response.json(content_type=None)
                    if meta.get("startDate"):
                        start = pd.Timestamp(meta["startDate"])
        except Exception:
            pass  # 元数据失败则退回默认起点

        full = await self._fetch_chunked(symbol, start, today)
        self._write_store(symbol, full)
        return full

    async def fetch_klines(
        self,
        symbol: str,
        interval: Interval,
        market_type: MarketType,
        start_time: datetime,
        end_time: datetime,
    ) -> pd.DataFrame:
        self._require_key(self.api_key)
        symbol = symbol.upper().strip()

        if interval != Interval.ONE_DAY and interval.value not in INTERVAL_RESAMPLE:
            raise Exception(f"美股数据源仅支持日线/周线/月线/季线（当前请求: {interval.value}）")

        df = await self._fetch_daily(symbol)

        if interval != Interval.ONE_DAY:
            df = resample_ohlcv(df, INTERVAL_RESAMPLE[interval.value])
            if not df.empty:
                df["interval"] = interval.value

        if df.empty:
            return df

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
        """返回预设的热门美股/ETF 列表"""
        return [
            {
                "symbol": ticker,
                "market_type": MarketType.SPOT.value,
                "base": ticker,
                "quote": "USD",
                "price_precision": 4,
            }
            for ticker in POPULAR_US_STOCKS
        ]

    async def get_futures_symbols(self, settle: str = "usdt") -> list[dict[str, Any]]:
        """美股无合约市场"""
        return []
