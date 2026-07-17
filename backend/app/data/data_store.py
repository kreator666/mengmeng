import os
from pathlib import Path

import pandas as pd


class DataStore:
    """本地数据存储：SQLite + Parquet 双格式，支持按 provider 分目录"""

    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _provider_dir(self, provider: str) -> Path:
        """返回某 provider 的缓存根目录"""
        provider_dir = self.cache_dir / provider
        provider_dir.mkdir(parents=True, exist_ok=True)
        return provider_dir

    def _cache_key(self, symbol: str, interval: str, market_type: str, provider: str) -> str:
        return f"{provider}_{symbol}_{interval}_{market_type}"

    def _sqlite_path(self, cache_key: str, provider: str) -> Path:
        sqlite_dir = self._provider_dir(provider) / "sqlite"
        sqlite_dir.mkdir(exist_ok=True)
        return sqlite_dir / f"{cache_key}.db"

    def _parquet_path(self, cache_key: str, provider: str) -> Path:
        parquet_dir = self._provider_dir(provider) / "parquet"
        parquet_dir.mkdir(exist_ok=True)
        return parquet_dir / f"{cache_key}.parquet"

    def _choose_format(self, df: pd.DataFrame | None = None, estimated_rows: int = 0) -> str:
        """根据数据量选择存储格式"""
        rows = len(df) if df is not None else estimated_rows
        return "parquet" if rows >= 1_000_000 else "sqlite"

    def save(
        self,
        df: pd.DataFrame,
        symbol: str,
        interval: str,
        market_type: str,
        provider: str = "gateio",
    ):
        """保存 K 线数据"""
        if df.empty:
            return

        cache_key = self._cache_key(symbol, interval, market_type, provider)
        fmt = self._choose_format(df)

        if fmt == "sqlite":
            path = self._sqlite_path(cache_key, provider)
            df.to_sql("klines", f"sqlite:///{path}", if_exists="replace", index=False)
        else:
            path = self._parquet_path(cache_key, provider)
            df.to_parquet(path, index=False, engine="pyarrow")

    def load(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        provider: str = "gateio",
    ) -> pd.DataFrame | None:
        """加载 K 线数据"""
        cache_key = self._cache_key(symbol, interval, market_type, provider)

        sqlite_path = self._sqlite_path(cache_key, provider)
        parquet_path = self._parquet_path(cache_key, provider)

        if parquet_path.exists():
            return pd.read_parquet(parquet_path)

        if sqlite_path.exists():
            df = pd.read_sql("SELECT * FROM klines", f"sqlite:///{sqlite_path}")
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            return df

        return None

    def exists(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        provider: str = "gateio",
    ) -> bool:
        cache_key = self._cache_key(symbol, interval, market_type, provider)
        return self._sqlite_path(cache_key, provider).exists() or self._parquet_path(
            cache_key, provider
        ).exists()

    def clear(
        self,
        symbol: str,
        interval: str,
        market_type: str,
        provider: str = "gateio",
    ):
        """清除缓存"""
        cache_key = self._cache_key(symbol, interval, market_type, provider)
        for path in [self._sqlite_path(cache_key, provider), self._parquet_path(cache_key, provider)]:
            if path.exists():
                path.unlink()
