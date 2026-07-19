import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from app.data.us_stock_client import USStockClient, resample_ohlcv
from app.models.enums import Interval, MarketType

# Tiingo /tiingo/daily/{ticker}/prices 响应样式
SAMPLE_PAYLOAD = [
    {
        "date": "2026-07-16T00:00:00.000Z",
        "open": 124.73, "high": 144.40, "low": 116.47, "close": 135.47, "volume": 105762347,
        "adjOpen": 124.73, "adjHigh": 144.40, "adjLow": 116.47, "adjClose": 135.47,
        "adjVolume": 105762347, "divCash": 0.0, "splitFactor": 1.0,
    },
    {
        "date": "2026-07-17T00:00:00.000Z",
        "open": 135.0, "high": 140.0, "low": 120.0, "close": 138.0, "volume": 90000000,
        "adjOpen": 135.0, "adjHigh": 140.0, "adjLow": 120.0, "adjClose": 138.0,
        "adjVolume": 90000000, "divCash": 0.0, "splitFactor": 1.0,
    },
]


def test_parse_prices():
    print("=" * 60)
    print("测试 Tiingo K 线解析")
    print("=" * 60)

    df = USStockClient._parse_prices(SAMPLE_PAYLOAD, "SOXL")
    print(df[["timestamp", "open", "high", "low", "close", "volume"]])

    assert len(df) == 2
    row = df.iloc[0]
    assert row["open"] == 124.73 and row["close"] == 135.47
    assert row["high"] == 144.40 and row["low"] == 116.47
    assert row["volume"] == 105762347
    assert df["timestamp"].iloc[0] < df["timestamp"].iloc[1]
    assert (df["symbol"] == "SOXL").all()

    empty = USStockClient._parse_prices([], "XXX")
    assert empty.empty

    print("[OK] 解析测试通过\n")


def test_resample_weekly_monthly():
    print("=" * 60)
    print("测试日 -> 周/月/季聚合")
    print("=" * 60)

    rows = []
    dates = pd.date_range("2024-01-01", periods=400, freq="D", tz="UTC")
    for i, ts in enumerate(dates):
        rows.append({
            "timestamp": ts, "open": 100 + i * 0.1, "high": 101 + i * 0.1,
            "low": 99 + i * 0.1, "close": 100.5 + i * 0.1, "volume": 1000,
            "market_type": "spot", "symbol": "SOXL", "interval": "1d",
        })
    df = pd.DataFrame(rows)

    weekly = resample_ohlcv(df, "W")
    monthly = resample_ohlcv(df, "MS")
    quarterly = resample_ohlcv(df, "QS")
    print(f"   日 {len(df)} -> 周 {len(weekly)} / 月 {len(monthly)} / 季 {len(quarterly)}")

    assert len(weekly) < len(df) and len(monthly) < len(weekly)
    assert len(quarterly) >= 5
    assert (weekly["high"] >= weekly["low"]).all()

    print("[OK] 聚合测试通过\n")


def test_interval_validation_and_key():
    print("=" * 60)
    print("测试周期校验与 key 检查")
    print("=" * 60)

    from datetime import datetime

    # 缺 key（显式传空字符串，绕过环境变量/配置文件）
    client = USStockClient(api_key="")

    async def run_missing_key():
        try:
            await client.fetch_klines("SOXL", Interval.ONE_DAY, MarketType.SPOT,
                                      datetime(2024, 1, 1), datetime(2024, 2, 1))
            return None
        except Exception as e:
            return str(e)

    err = asyncio.run(run_missing_key())
    print(f"   缺 key 报错: {err[:60]}...")
    assert "TIINGO_API_KEY" in err

    # 不支持的周期（小时级）
    client2 = USStockClient(api_key="dummy")

    async def run_bad_interval():
        try:
            await client2.fetch_klines("SOXL", Interval.ONE_HOUR, MarketType.SPOT,
                                       datetime(2024, 1, 1), datetime(2024, 2, 1))
            return None
        except Exception as e:
            return str(e)

    err2 = asyncio.run(run_bad_interval())
    print(f"   小时级报错: {err2}")
    assert err2 is not None and "仅支持日线/周线/月线/季线" in err2

    print("[OK] 校验测试通过\n")


if __name__ == "__main__":
    test_parse_prices()
    test_resample_weekly_monthly()
    test_interval_validation_and_key()
    print("全部美股数据源测试通过")
