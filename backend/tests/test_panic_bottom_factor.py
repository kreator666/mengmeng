import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import numpy as np

from app.core.factor_engine import eval_python_code, signal_to_position
from app.core.backtest_engine import vectorized_backtest
from app.core.cost_model import CostModel
from app.models.enums import PositionMode


def _make_synthetic_data():
    """
    构造包含恐慌抄底特征的合成 K 线数据

    前 15 根：正常上涨
    第 16-18 根：连续大跌，第 18 根制造长下影线 + 放量 + 破底翻
    """
    dates = pd.date_range("2024-01-01", periods=30, freq="h")
    data = []
    close = 100.0
    for i in range(30):
        if i < 15:
            open_p = close
            close = close * 1.005
            high = max(open_p, close) * 1.002
            low = min(open_p, close) * 0.998
            volume = 1000
        elif i < 17:
            open_p = close
            close = close * 0.92
            high = max(open_p, close) * 1.005
            low = min(open_p, close) * 0.99
            volume = 1200
        elif i == 17:
            # 恐慌探底：开盘价大跌，随后拉起，形成长下影线
            open_p = close * 0.90
            low = open_p * 0.88
            close = open_p * 0.98
            high = open_p * 1.01
            volume = 5000
        else:
            open_p = close
            close = close * 1.01
            high = max(open_p, close) * 1.005
            low = min(open_p, close) * 0.995
            volume = 1500

        data.append({
            "timestamp": dates[i],
            "open": open_p,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
        })

    return pd.DataFrame(data)


def test_backend_module_factor():
    print("=" * 60)
    print("测试恐慌抄底因子：后端模块")
    print("=" * 60)

    from app.core.panic_bottom_factor import factor

    df = _make_synthetic_data()
    signal = factor(df)
    positive_count = (signal > 0).sum()

    print(f"   K 线数量: {len(df)}")
    print(f"   触发信号数量: {positive_count}")
    print(f"   最大信号强度: {signal.max():.2f}")

    assert positive_count > 0, "应至少触发一次恐慌抄底信号"
    assert signal.max() >= 50, "信号强度应 >= 50"

    print("[OK] 后端模块测试通过\n")


def test_paste_ready_code_in_sandbox():
    print("=" * 60)
    print("测试恐慌抄底因子：粘贴代码兼容沙箱")
    print("=" * 60)

    from app.core.panic_bottom_factor import PASTE_READY_CODE

    df = _make_synthetic_data()
    signal = eval_python_code(df, PASTE_READY_CODE)
    positive_count = (signal > 0).sum()

    print(f"   K 线数量: {len(df)}")
    print(f"   触发信号数量: {positive_count}")
    print(f"   最大信号强度: {signal.max():.2f}")

    assert positive_count > 0, "粘贴代码应在沙箱中触发信号"
    assert signal.max() >= 50, "粘贴代码信号强度应 >= 50"

    print("[OK] 沙箱粘贴代码测试通过\n")


def test_factor_with_backtest_engine():
    print("=" * 60)
    print("测试恐慌抄底因子：接入回测引擎")
    print("=" * 60)

    from app.core.panic_bottom_factor import factor

    df = _make_synthetic_data()
    signal = factor(df)
    position = signal_to_position(signal, allow_short=False)

    result_df = vectorized_backtest(
        df=df,
        signal=signal,
        initial_capital=10000.0,
        position_mode=PositionMode.FIXED_RATIO,
        position_ratio=0.95,
        cost_model=CostModel(fee_rate=0.002, slippage=0.0005),
        allow_short=False,
    )

    print(f"   最终资金: {result_df['equity_curve'].iloc[-1]:.2f}")
    print(f"   总收益率: {(result_df['equity_curve'].iloc[-1] / 10000 - 1) * 100:.2f}%")
    print(f"   触发交易次数: {(result_df['trades'] > 0).sum()}")

    assert result_df["equity_curve"].iloc[-1] > 0, "资金曲线应大于 0"

    print("[OK] 回测引擎接入测试通过\n")


def test_original_factor_file_factor():
    print("=" * 60)
    print("测试恐慌抄底因子：原始 factor/panic_bottom_factors.py")
    print("=" * 60)

    factor_root = Path(__file__).parent.parent.parent / "factor"
    sys.path.insert(0, str(factor_root))
    from panic_bottom_factors import factor

    df = _make_synthetic_data()
    signal = factor(df)
    positive_count = (signal > 0).sum()

    print(f"   K 线数量: {len(df)}")
    print(f"   触发信号数量: {positive_count}")
    print(f"   最大信号强度: {signal.max():.2f}")

    assert positive_count > 0, "原始文件 factor(df) 应触发信号"

    print("[OK] 原始文件测试通过\n")


if __name__ == "__main__":
    test_backend_module_factor()
    test_paste_ready_code_in_sandbox()
    test_factor_with_backtest_engine()
    test_original_factor_file_factor()
    print("全部恐慌抄底因子测试通过")
