import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np

from app.core.factor_engine import eval_python_code
from app.core.backtest_engine import vectorized_backtest
from app.core.cost_model import CostModel
from app.models.enums import PositionMode


def _support_at(rows, lookback=60):
    """按策略公式计算当前支撑位：取已有历史最后 lookback 根"""
    window = rows[-lookback:]
    range_high = max(r["high"] for r in window)
    range_low = min(r["low"] for r in window)
    return (range_high - range_low) / 3 + range_low


def _make_synthetic_data():
    """
    构造包含支撑位策略特征的合成 K 线数据

    第 0-69 根：稳步上涨，形成区间
    第 70-72 根：回调，最后一根盘中回踩支撑位但收盘守住 -> 触发入场
    第 73-82 根：反弹上涨（持仓期）
    第 83 根：收盘跌破支撑位 -> 触发离场
    """
    dates = pd.date_range("2024-01-01", periods=90, freq="h")
    rows = []
    close = 100.0

    def add(i, open_p, high, low, close_p, volume=1000):
        rows.append({
            "timestamp": dates[i],
            "open": open_p,
            "high": high,
            "low": low,
            "close": close_p,
            "volume": volume,
        })

    # 阶段 1：稳步上涨 70 根
    for i in range(70):
        open_p = close
        close = close * 1.008
        add(i, open_p, max(open_p, close) * 1.002, min(open_p, close) * 0.998, close)

    # 阶段 2：回调至支撑位附近
    for i in range(70, 72):
        open_p = close
        close = close * 0.97
        add(i, open_p, max(open_p, close) * 1.002, min(open_p, close) * 0.998, close)

    # 回踩确认 K 线：低点探到支撑位下方一点点，收盘守在支撑之上
    support = _support_at(rows)
    open_p = close
    add(72, open_p, open_p * 1.005, support * 0.998, support * 1.01, volume=2500)
    close = support * 1.01

    # 阶段 3：反弹 10 根
    for i in range(73, 83):
        open_p = close
        close = close * 1.01
        add(i, open_p, max(open_p, close) * 1.002, min(open_p, close) * 0.998, close)

    # 阶段 4：收盘跌破支撑位，触发离场
    support = _support_at(rows)
    open_p = close
    close = support * 0.95
    add(83, open_p, open_p * 1.002, close * 0.995, close, volume=2000)

    # 收尾：低位横盘
    for i in range(84, 90):
        open_p = close
        close = close * 1.001
        add(i, open_p, max(open_p, close) * 1.002, min(open_p, close) * 0.998, close)

    return pd.DataFrame(rows)


def test_backend_module_factor():
    print("=" * 60)
    print("测试支撑位策略：后端模块")
    print("=" * 60)

    from app.core.support_level_factor import factor

    df = _make_synthetic_data()
    signal = factor(df)
    positive_count = (signal > 0).sum()

    print(f"   K 线数量: {len(df)}")
    print(f"   持仓 K 线数量: {positive_count}")
    print(f"   首次入场位置: {int((signal > 0).idxmax()) if positive_count else '无'}")

    assert positive_count > 0, "回踩支撑位守住应触发入场"
    # 回踩确认 K 线（第 72 根）应已入场
    assert signal.iloc[72] > 0, "第 72 根回踩守住支撑应入场"
    # 反弹期间应持续持仓
    assert signal.iloc[80] > 0, "反弹期间应持续持仓"
    # 跌破支撑后应离场
    assert (signal.iloc[84:] == 0).all(), "收盘跌破支撑后应离场且不再入场"

    print("[OK] 后端模块测试通过\n")


def test_paste_ready_code_in_sandbox():
    print("=" * 60)
    print("测试支撑位策略：粘贴代码兼容沙箱")
    print("=" * 60)

    from app.core.support_level_factor import PASTE_READY_CODE

    df = _make_synthetic_data()
    signal = eval_python_code(df, PASTE_READY_CODE)
    positive_count = (signal > 0).sum()

    print(f"   K 线数量: {len(df)}")
    print(f"   持仓 K 线数量: {positive_count}")

    assert positive_count > 0, "粘贴代码应在沙箱中触发入场"
    assert signal.iloc[72] > 0, "粘贴代码第 72 根应入场"
    assert (signal.iloc[84:] == 0).all(), "粘贴代码破位后应离场"

    print("[OK] 沙箱粘贴代码测试通过\n")


def test_factor_with_backtest_engine():
    print("=" * 60)
    print("测试支撑位策略：接入回测引擎")
    print("=" * 60)

    from app.core.support_level_factor import factor

    df = _make_synthetic_data()
    signal = factor(df)

    result_df = vectorized_backtest(
        df=df,
        signal=signal,
        initial_capital=10000.0,
        position_mode=PositionMode.FIXED_RATIO,
        position_ratio=0.95,
        cost_model=CostModel(fee_rate=0.002, slippage=0.0005),
        allow_short=False,
    )

    final_equity = result_df["equity_curve"].iloc[-1]
    print(f"   最终资金: {final_equity:.2f}")
    print(f"   总收益率: {(final_equity / 10000 - 1) * 100:.2f}%")
    print(f"   触发交易次数: {(result_df['trades'] > 0).sum()}")

    assert final_equity > 0, "资金曲线应大于 0"
    assert (result_df["trades"] > 0).sum() >= 2, "应至少有一次买入和一次卖出"

    print("[OK] 回测引擎接入测试通过\n")


if __name__ == "__main__":
    test_backend_module_factor()
    test_paste_ready_code_in_sandbox()
    test_factor_with_backtest_engine()
    print("全部支撑位策略测试通过")
