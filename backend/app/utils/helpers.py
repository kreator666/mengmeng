import hashlib
import hmac
import time
from datetime import date, datetime
from typing import Any

import pandas as pd


def to_unix_timestamp(dt: datetime | date) -> int:
    """将 datetime/date 转换为 Unix 秒级时间戳"""
    if isinstance(dt, date) and not isinstance(dt, datetime):
        dt = datetime.combine(dt, datetime.min.time())
    return int(dt.timestamp())


def normalize_ohlcv(
    raw_data: list[list[Any]],
    market_type: str,
    symbol: str,
    interval: str,
    column_order: list[str],
) -> pd.DataFrame:
    """
    将 Gate.io 返回的 K 线数组标准化为统一 OHLCV DataFrame
    column_order: 原始数据列顺序，例如 ['timestamp', 'volume', 'close', 'high', 'low', 'open']
    如果返回数据列数多于 column_order，只取前 len(column_order) 列
    """
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

    # 只取预期的列数
    expected_cols = len(column_order)
    trimmed_data = [row[:expected_cols] for row in raw_data]

    df = pd.DataFrame(trimmed_data, columns=column_order)
    df["timestamp"] = pd.to_numeric(df["timestamp"], errors="coerce")
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s", utc=True)
    df = df.sort_values("timestamp").reset_index(drop=True)

    # 确保数值类型
    for col in ["open", "high", "low", "close", "volume"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["market_type"] = market_type
    df["symbol"] = symbol
    df["interval"] = interval

    return df[["timestamp", "open", "high", "low", "close", "volume", "market_type", "symbol", "interval"]]


def generate_signature(secret: str, payload: str) -> str:
    """生成 HMAC-SHA512 签名"""
    return hmac.new(
        secret.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha512,
    ).hexdigest()


def now_ms() -> int:
    return int(time.time() * 1000)
