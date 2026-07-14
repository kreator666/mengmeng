from datetime import datetime, timedelta, timezone
from typing import Any

import pandas as pd

from app.data.data_store import DataStore
from app.data.gateio_client import GateIOClient
from app.models.enums import Interval, MarketType
from app.utils.helpers import to_unix_timestamp


def _to_utc(dt: datetime) -> datetime:
    """将 datetime 转换为 UTC aware datetime"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


class CacheManager:
    """
    K 线缓存管理器：缓存优先、按需补全
    """

    def __init__(self, store: DataStore | None = None, client: GateIOClient | None = None):
        self.store = store or DataStore()
        self.client = client or GateIOClient()

    def _cached_range(self, df: pd.DataFrame | None) -> tuple[datetime, datetime] | None:
        if df is None or df.empty:
            return None
        return _to_utc(df["timestamp"].min().to_pydatetime()), _to_utc(df["timestamp"].max().to_pydatetime())

    def _merge_data(
        self,
        cached_df: pd.DataFrame | None,
        fetched_df: pd.DataFrame,
    ) -> pd.DataFrame:
        """合并缓存数据与新拉取数据"""
        if cached_df is None or cached_df.empty:
            return fetched_df

        combined = pd.concat([cached_df, fetched_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
        combined = combined.sort_values("timestamp").reset_index(drop=True)
        return combined

    async def get_klines(
        self,
        symbol: str,
        interval: Interval,
        market_type: MarketType,
        start_time: datetime,
        end_time: datetime,
    ) -> pd.DataFrame:
        """
        获取 K 线数据，优先使用缓存，缺失部分从 API 补全
        """
        symbol = symbol.upper()
        start_utc = _to_utc(start_time)
        end_utc = _to_utc(end_time)

        cached_df = self.store.load(symbol, interval.value, market_type.value)
        cached_range = self._cached_range(cached_df)

        # 情况 1：完全命中
        if cached_range and cached_range[0] <= start_utc and cached_range[1] >= end_utc:
            return self._filter_range(cached_df, start_utc, end_utc)

        # 情况 2：完全未命中
        if cached_df is None or cached_df.empty:
            fetched_df = await self.client.fetch_klines(symbol, interval, market_type, start_utc, end_utc)
            if not fetched_df.empty:
                self.store.save(fetched_df, symbol, interval.value, market_type.value)
            return fetched_df

        # 情况 3：部分缺失，需要补充
        missing_ranges = self._compute_missing_ranges(cached_range, start_utc, end_utc)
        fetched_dfs: list[pd.DataFrame] = []

        for missing_start, missing_end in missing_ranges:
            df = await self.client.fetch_klines(symbol, interval, market_type, missing_start, missing_end)
            if not df.empty:
                fetched_dfs.append(df)

        if fetched_dfs:
            all_fetched = pd.concat(fetched_dfs, ignore_index=True)
            merged = self._merge_data(cached_df, all_fetched)
            self.store.save(merged, symbol, interval.value, market_type.value)
        else:
            merged = cached_df

        return self._filter_range(merged, start_utc, end_utc)

    def _filter_range(self, df: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
        mask = (df["timestamp"] >= pd.Timestamp(start)) & (df["timestamp"] <= pd.Timestamp(end))
        return df.loc[mask].reset_index(drop=True)

    def _compute_missing_ranges(
        self,
        cached_range: tuple[datetime, datetime] | None,
        start: datetime,
        end: datetime,
    ) -> list[tuple[datetime, datetime]]:
        """计算需要补充的时间区间"""
        if cached_range is None:
            return [(start, end)]

        ranges = []
        cache_start, cache_end = cached_range

        if start < cache_start:
            ranges.append((start, cache_start - timedelta(seconds=1)))
        if end > cache_end:
            ranges.append((cache_end + timedelta(seconds=1), end))

        return ranges

    async def close(self):
        await self.client.close()
