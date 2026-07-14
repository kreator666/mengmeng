import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np

from app.core.backtest_engine import vectorized_backtest
from app.core.performance import extract_trades


def _make_data():
    """构造测试数据：第1根入场，第2根大跌触发止损，第3根涨回"""
    dates = pd.date_range("2024-01-01", periods=5, freq="h")
    data = [
        {"timestamp": dates[0], "open": 100, "high": 102, "low": 99, "close": 100, "volume": 1000},
        {"timestamp": dates[1], "open": 100, "high": 100, "low": 90, "close": 91, "volume": 1000},  # 触发5%止损
        {"timestamp": dates[2], "open": 91, "high": 110, "low": 91, "close": 110, "volume": 1000},  # 触发10%止盈
        {"timestamp": dates[3], "open": 110, "high": 110, "low": 100, "close": 105, "volume": 1000},
        {"timestamp": dates[4], "open": 105, "high": 105, "low": 100, "close": 102, "volume": 1000},
    ]
    return pd.DataFrame(data)


def test_stop_loss():
    print("=" * 60)
    print("测试止损逻辑")
    print("=" * 60)

    df = _make_data()
    signal = pd.Series([1, 1, 1, 1, 1], index=df.index)

    result = vectorized_backtest(
        df=df,
        signal=signal,
        initial_capital=10000.0,
        stop_loss=0.05,
        take_profit=0.0,
        max_holding_bars=0,
    )

    trades = extract_trades(result)
    print(f"   交易次数: {len(trades)}")
    if trades:
        print(f"   入场价: {trades[0]['entry_price']}")
        print(f"   出场价: {trades[0]['exit_price']}")
        print(f"   收益率: {trades[0]['return_pct']:.4f}")
        assert trades[0]["exit_price"] == 95.0, "应触发5%止损，出场价95"
        assert abs(trades[0]["return_pct"] - (-0.05)) < 1e-6

    print("[OK] 止损测试通过")


def test_take_profit():
    print("=" * 60)
    print("测试止盈逻辑")
    print("=" * 60)

    df = _make_data()
    signal = pd.Series([1, 1, 1, 1, 1], index=df.index)

    result = vectorized_backtest(
        df=df,
        signal=signal,
        initial_capital=10000.0,
        stop_loss=0.0,
        take_profit=0.10,
        max_holding_bars=0,
    )

    trades = extract_trades(result)
    print(f"   交易次数: {len(trades)}")
    if trades:
        print(f"   入场价: {trades[0]['entry_price']}")
        print(f"   出场价: {trades[0]['exit_price']}")
        print(f"   收益率: {trades[0]['return_pct']:.4f}")
        assert trades[0]["exit_price"] == 110.0, "应触发10%止盈，出场价110"
        assert abs(trades[0]["return_pct"] - 0.10) < 1e-6

    print("[OK] 止盈测试通过")


def test_max_holding_bars():
    print("=" * 60)
    print("测试最大持仓周期")
    print("=" * 60)

    df = _make_data()
    signal = pd.Series([1, 1, 1, 1, 1], index=df.index)

    result = vectorized_backtest(
        df=df,
        signal=signal,
        initial_capital=10000.0,
        stop_loss=0.0,
        take_profit=0.0,
        max_holding_bars=2,
    )

    trades = extract_trades(result)
    print(f"   交易次数: {len(trades)}")
    if trades:
        print(f"   入场时间: {trades[0]['entry_time']}")
        print(f"   出场时间: {trades[0]['exit_time']}")
        assert len(trades) == 1

    print("[OK] 最大持仓周期测试通过")


def test_signal_off_does_not_exit():
    print("=" * 60)
    print("测试：启用止损止盈后，信号消失不应平仓")
    print("=" * 60)

    dates = pd.date_range("2024-01-01", periods=5, freq="h")
    data = []
    for i in range(5):
        data.append({
            "timestamp": dates[i],
            "open": 100 + i,
            "high": 100 + i + 1,
            "low": 100 + i - 1,
            "close": 100 + i,
            "volume": 1000,
        })
    df = pd.DataFrame(data)
    # 信号只在第 0 根为正，之后消失；但止盈设为 5% 应持有到触发
    signal = pd.Series([1, 0, 0, 0, 0], index=df.index)

    result = vectorized_backtest(
        df=df,
        signal=signal,
        initial_capital=10000.0,
        stop_loss=0.0,
        take_profit=0.05,
        max_holding_bars=0,
    )

    trades = extract_trades(result)
    print(f"   交易次数: {len(trades)}")
    if trades:
        print(f"   入场价: {trades[0]['entry_price']}")
        print(f"   出场价: {trades[0]['exit_price']}")
        print(f"   收益率: {trades[0]['return_pct'] * 100:.2f}%")
        assert trades[0]["exit_price"] == 105.0, "应按5%止盈出场"

    print("[OK] 信号消失不平仓测试通过")


if __name__ == "__main__":
    test_stop_loss()
    test_take_profit()
    test_max_holding_bars()
    test_signal_off_does_not_exit()
    print("全部止损止盈测试通过")
