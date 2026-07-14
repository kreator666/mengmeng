import os
from pathlib import Path

import pandas as pd


class DataStore:
    """本地数据存储：SQLite + Parquet 双格式"""

    def __init__(self, cache_dir: str = "data/cache"):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.sqlite_dir = self.cache_dir / "sqlite"
        self.parquet_dir = self.cache_dir / "parquet"
        self.sqlite_dir.mkdir(exist_ok=True)
        self.parquet_dir.mkdir(exist_ok=True)

    def _cache_key(self, symbol: str, interval: str, market_type: str) -> str:
        return f"{symbol}_{interval}_{market_type}"

    def _sqlite_path(self, cache_key: str) -> Path:
        return self.sqlite_dir / f"{cache_key}.db"

    def _parquet_path(self, cache_key: str) -> Path:
        return self.parquet_dir / f"{cache_key}.parquet"

    def _choose_format(self, df: pd.DataFrame | None = None, estimated_rows: int = 0) -> str:
        """根据数据量选择存储格式"""
        rows = len(df) if df is not None else estimated_rows
        return "parquet" if rows >= 1_000_000 else "sqlite"

    def save(self, df: pd.DataFrame, symbol: str, interval: str, market_type: str):
        """保存 K 线数据"""
        if df.empty:
            return

        cache_key = self._cache_key(symbol, interval, market_type)
        fmt = self._choose_format(df)

        if fmt == "sqlite":
            path = self._sqlite_path(cache_key)
            df.to_sql("klines", f"sqlite:///{path}", if_exists="replace", index=False)
        else:
            path = self._parquet_path(cache_key)
            df.to_parquet(path, index=False, engine="pyarrow")

    def load(self, symbol: str, interval: str, market_type: str) -> pd.DataFrame | None:
        """加载 K 线数据"""
        cache_key = self._cache_key(symbol, interval, market_type)

        sqlite_path = self._sqlite_path(cache_key)
        parquet_path = self._parquet_path(cache_key)

        if parquet_path.exists():
            return pd.read_parquet(parquet_path)

        if sqlite_path.exists():
            df = pd.read_sql("SELECT * FROM klines", f"sqlite:///{sqlite_path}")
            df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
            return df

        return None

    def exists(self, symbol: str, interval: str, market_type: str) -> bool:
        cache_key = self._cache_key(symbol, interval, market_type)
        return self._sqlite_path(cache_key).exists() or self._parquet_path(cache_key).exists()

    def clear(self, symbol: str, interval: str, market_type: str):
        """清除缓存"""
        cache_key = self._cache_key(symbol, interval, market_type)
        for path in [self._sqlite_path(cache_key), self._parquet_path(cache_key)]:
            if path.exists():
                path.unlink()
