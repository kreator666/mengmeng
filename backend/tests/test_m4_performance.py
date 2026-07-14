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
from app.models.enums import Interval, MarketType, PositionMode


async def test_performance():
    print("=" * 60)
    print("测试 M4 绩效分析")
    print("=" * 60)

    manager = CacheManager()
    try:
        end = datetime.utcnow().replace(minute=0, second=0, microsecond=0)
        start = end - timedelta(days=60)

        print(f"\n1. 拉取 BTC_USDT 1h 数据 ({start.date()} ~ {end.date()})")
        df = await manager.get_klines("BTC_USDT", Interval.ONE_HOUR, MarketType.SPOT, start, end)
        print(f"   获取 {len(df)} 条 K 线")

        print("\n2. 执行双均线金叉策略回测")
        signal = eval_formula(df, "AND(EMA(close, 12) > EMA(close, 26), RSI(close, 14) < 70)")
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

        print("\n3. 验证绩效指标")
        summary = calculate_performance(result_df, 10000.0)
        required_keys = [
            "total_return", "annualized_return", "max_drawdown", "max_drawdown_duration",
            "volatility", "downside_volatility", "sharpe_ratio", "sortino_ratio",
            "calmar_ratio", "total_trades", "win_rate", "profit_factor",
            "avg_trade_return", "alpha",
        ]
        for key in required_keys:
            assert key in summary, f"缺少指标: {key}"
            print(f"   {key}: {summary[key]}")

        print("\n4. 验证交易记录")
        trades = extract_trades(result_df)
        assert len(trades) == summary["total_trades"], "交易记录数量与绩效指标不一致"
        print(f"   交易次数: {len(trades)}")
        if trades:
            required_trade_keys = ["entry_time", "exit_time", "side", "entry_price", "exit_price", "pnl", "return_pct"]
            for key in required_trade_keys:
                assert key in trades[0], f"交易记录缺少字段: {key}"
            print(f"   首笔交易: {trades[0]}")

        print("\n5. 验证资金曲线与回撤序列")
        assert "equity_curve" in result_df.columns
        assert "net_returns" in result_df.columns
        print(f"   资金曲线长度: {len(result_df)}")
        print(f"   最终资金: {result_df['equity_curve'].iloc[-1]:.2f}")

        print("\n[OK] M4 绩效分析测试通过")

    except Exception as e:
        print(f"\n[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await manager.close()


if __name__ == "__main__":
    asyncio.run(test_performance())
