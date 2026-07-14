import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.data.gateio_client import GateIOClient
from app.models.enums import Interval, MarketType


async def test_market(client: GateIOClient, market_type: MarketType, label: str):
    print(f"\n测试 {label}")
    end = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
    start = end - timedelta(hours=24)
    df = await client.fetch_klines("BTC_USDT", Interval.ONE_HOUR, market_type, start, end)
    print(f"   获取 {len(df)} 条 K 线")
    if not df.empty:
        print(f"   时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
        print(f"   最新收盘价: {df['close'].iloc[-1]}")


async def test_connection():
    print("=" * 60)
    print("测试 Gate.io API 连接")
    print("=" * 60)

    client = GateIOClient()
    try:
        print("\n1. 测试获取现货交易对列表")
        symbols = await client.get_spot_symbols()
        print(f"   成功获取 {len(symbols)} 个交易对")
        print(f"   前 3 个: {[s.get('id') for s in symbols[:3]]}")

        print("\n2. 测试现货 K 线")
        await test_market(client, MarketType.SPOT, "现货 BTC_USDT 1h")

        print("\n3. 测试 USDT 合约 K 线")
        await test_market(client, MarketType.FUTURES_USDT, "USDT 合约 BTC_USDT 1h")

        print("\n[OK] Gate.io API 连接正常")
    except Exception as e:
        print(f"\n[FAIL] 连接失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(test_connection())
