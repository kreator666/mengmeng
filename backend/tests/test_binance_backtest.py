import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.backtest_engine import vectorized_backtest
from app.core.cost_model import CostModel
from app.core.factor_engine import eval_formula
from app.core.performance import calculate_performance, extract_trades
from app.data.cache_manager import CacheManager
from app.models.enums import Interval, MarketType, PositionMode, Provider


async def test_binance_long_backtest():
    print("=" * 60)
    print("测试 Binance 长周期回测")
    print("=" * 60)

    manager = CacheManager(provider=Provider.BINANCE)
    try:
        end = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        start = end - timedelta(days=365 * 3)

        print(f"\n1. 从 Binance 拉取 BTC_USDT 1h 数据 ({start.date()} ~ {end.date()})")
        df = await manager.get_klines("BTC_USDT", Interval.ONE_HOUR, MarketType.SPOT, start, end)
        print(f"   获取 {len(df)} 条 K 线")
        print(f"   时间范围: {df['timestamp'].min()} ~ {df['timestamp'].max()}")
        assert len(df) > 20000, "长周期数据不足"

        print("\n2. 构建双均线金叉信号")
        signal = eval_formula(df, "EMA(close, 12) > EMA(close, 26)")
        print(f"   信号非零数量: {(signal != 0).sum()}")

        print("\n3. 执行向量化回测")
        cost_model = CostModel(fee_rate=0.002, slippage=0.0005)
        result_df = vectorized_backtest(
            df=df,
            signal=signal,
            initial_capital=10000.0,
            position_mode=PositionMode.FIXED_RATIO,
            position_ratio=0.95,
            cost_model=cost_model,
            allow_short=False,
        )
        print(f"   资金曲线最终值: {result_df['equity_curve'].iloc[-1]:.2f}")
        print(f"   总收益率: {(result_df['equity_curve'].iloc[-1] / 10000 - 1) * 100:.2f}%")

        print("\n4. 计算绩效指标")
        summary = calculate_performance(result_df, 10000.0)
        print(f"   总收益率: {summary['total_return']:.4f}")
        print(f"   年化收益率: {summary['annualized_return']:.4f}")
        print(f"   最大回撤: {summary['max_drawdown']:.4f}")
        print(f"   交易次数: {summary['total_trades']}")

        print("\n5. 提取交易记录")
        trades = extract_trades(result_df)
        print(f"   交易次数: {len(trades)}")

        print("\n[OK] Binance 长周期回测测试通过")

    except Exception as e:
        print(f"\n[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(test_binance_long_backtest())
