import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.data.cache_manager import CacheManager
from app.models.enums import Interval, MarketType


async def test_data_layer():
    manager = CacheManager()
    try:
        print("=" * 60)
        print("测试 M1 数据层：Gate.io 数据拉取与缓存")
        print("=" * 60)

        symbol = "BTC_USDT"
        interval = Interval.ONE_HOUR
        market_type = MarketType.SPOT

        # 使用最近的数据，避免 Gate.io 10000 个数据点限制
        end = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        start = end - timedelta(days=7)

        print(f"\n1. 首次拉取 {symbol} {interval.value} 数据 ({start.date()} ~ {end.date()})")
        df1 = await manager.get_klines(symbol, interval, market_type, start, end)
        print(f"   获取 {len(df1)} 条 K 线")
        print(f"   时间范围: {df1['timestamp'].min()} ~ {df1['timestamp'].max()}")
        print(f"   列: {list(df1.columns)}")
        print(f"   前 3 行:\n{df1.head(3)}")

        print(f"\n2. 重复请求同一区间（应命中缓存）")
        df2 = await manager.get_klines(symbol, interval, market_type, start, end)
        print(f"   获取 {len(df2)} 条 K 线")

        print(f"\n3. 扩展时间范围测试部分缺失")
        start2 = end - timedelta(days=10)
        df3 = await manager.get_klines(symbol, interval, market_type, start2, end)
        print(f"   获取 {len(df3)} 条 K 线")
        print(f"   时间范围: {df3['timestamp'].min()} ~ {df3['timestamp'].max()}")

        print("\n4. 数据标准化验证")
        required_cols = ["timestamp", "open", "high", "low", "close", "volume", "market_type", "symbol", "interval"]
        assert all(col in df1.columns for col in required_cols), "缺少必要列"
        print(f"   [OK] 标准化列检查通过")

        print("\n5. 数据类型验证")
        assert df1["open"].dtype in ["float64", "float32"]
        assert df1["close"].dtype in ["float64", "float32"]
        print(f"   [OK] 数值类型检查通过")

        print("\n[OK] M1 数据层测试通过")

    except Exception as e:
        print(f"\n[FAIL] 测试失败: {e}")
        import traceback

        traceback.print_exc()
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(test_data_layer())
