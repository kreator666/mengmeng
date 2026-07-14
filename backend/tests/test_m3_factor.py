import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.factor_engine import (
    calculate_ic,
    combine_factors_equal,
    combine_factors_weighted,
    eval_formula,
    eval_python_code,
    get_builtin_factors,
    signal_to_position,
)
from app.data.cache_manager import CacheManager
from app.models.enums import Interval, MarketType


async def test_factor_engine():
    print("=" * 60)
    print("测试 M3 因子引擎")
    print("=" * 60)

    manager = CacheManager()
    try:
        end = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        start = end - timedelta(days=30)

        print(f"\n1. 拉取 BTC_USDT 1h 数据 ({start.date()} ~ {end.date()})")
        df = await manager.get_klines("BTC_USDT", Interval.ONE_HOUR, MarketType.SPOT, start, end)
        print(f"   获取 {len(df)} 条 K 线")

        print("\n2. 测试公式模式")
        signal1 = eval_formula(df, "EMA(close, 12) > EMA(close, 26)")
        print(f"   双均线金叉信号非零数量: {(signal1 != 0).sum()}")

        signal2 = eval_formula(df, "RSI(close, 14) < 30")
        print(f"   RSI超卖信号非零数量: {(signal2 != 0).sum()}")

        signal3 = eval_formula(df, "(close - SMA(close, 20)) / STD(close, 20) > 2")
        print(f"   布林带偏离信号非零数量: {(signal3 != 0).sum()}")

        print("\n3. 测试 Python 代码模式")
        code = """
def factor(df):
    momentum = df['close'].pct_change(10)
    volatility = df['close'].rolling(20).std() / df['close']
    vol_ma = df['volume'].rolling(5).mean() / df['volume'].rolling(20).mean()
    signal = 0.5 * momentum + 0.3 * (1/volatility) + 0.2 * vol_ma
    return signal
"""
        signal_py = eval_python_code(df, code)
        print(f"   Python 代码信号非 NaN 数量: {signal_py.notna().sum()}")

        print("\n4. 测试多因子组合")
        f1 = eval_formula(df, "MOM(close, 10)")
        f2 = eval_formula(df, "RSI(close, 14)")
        f3 = eval_formula(df, "VOL_MA(volume, 5)")

        equal_weight = combine_factors_equal([f1, f2, f3])
        print(f"   等权组合信号非 NaN 数量: {equal_weight.notna().sum()}")

        weighted = combine_factors_weighted([f1, f2, f3], [0.5, 0.3, 0.2])
        print(f"   加权组合信号非 NaN 数量: {weighted.notna().sum()}")

        print("\n5. 测试信号转仓位")
        pos = signal_to_position(weighted, allow_short=False)
        print(f"   做多仓位数量: {(pos > 0).sum()}")

        print("\n6. 测试 IC 分析")
        returns = df["close"].pct_change()
        ic = calculate_ic(weighted, returns)
        print(f"   IC 值: {ic:.4f}")

        print("\n7. 测试内置因子列表")
        builtins = get_builtin_factors()
        print(f"   内置因子数量: {len(builtins)}")
        print(f"   前 3 个因子: {[f['name'] for f in builtins[:3]]}")

        print("\n[OK] M3 因子引擎测试通过")

    except Exception as e:
        print(f"\n[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(test_factor_engine())
