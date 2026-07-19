import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
import pandas as pd

from app.core.factor_engine import eval_python_code, signal_to_position
from app.core.backtest_engine import vectorized_backtest
from app.core.cost_model import CostModel
from app.models.enums import PositionMode


def _make_synthetic_data():
    """
    构造包含链风险特征的合成 K 线数据（日线）

    前 140 根：稳步上涨
    最后 3 根：连续暴跌（-3%, -6%, -8%），末日放量，触发传染预警
    """
    rets = [0.4] * 140 + [0.0] * 2 + [-3.0, -6.0, -8.0]
    n = len(rets)
    dates = pd.bdate_range("2025-01-01", periods=n)
    closes = 100.0 * np.cumprod(1 + np.array(rets) / 100)
    data = []
    prev = 100.0
    for i in range(n):
        close = closes[i]
        open_p = prev
        high = max(open_p, close) * 1.005
        low = min(open_p, close) * 0.995
        vol = 1000.0 * (3 if rets[i] <= -7 else 1)
        data.append({"timestamp": dates[i], "open": open_p, "high": high,
                     "low": low, "close": close, "volume": vol})
        prev = close
    return pd.DataFrame(data)


def test_backend_module_factor():
    print("=" * 60)
    print("测试算力链哨兵因子：后端模块")
    print("=" * 60)

    from app.core.openai_chain_sentinel_factor import factor

    df = _make_synthetic_data()
    signal = factor(df)
    positive_count = (signal > 0).sum()

    print(f"   K 线数量: {len(df)}")
    print(f"   触发信号数量: {positive_count}")
    print(f"   最大信号强度: {signal.max():.2f}")

    assert positive_count > 0, "暴跌日应触发链风险信号"
    assert signal.max() >= 50, "信号强度应 >= 50"
    assert len(signal) == len(df), "信号长度应与 K 线一致"

    print("[OK] 后端模块测试通过\n")


def test_paste_ready_code_in_sandbox():
    print("=" * 60)
    print("测试算力链哨兵因子：粘贴代码兼容沙箱")
    print("=" * 60)

    from app.core.openai_chain_sentinel_factor import PASTE_READY_CODE

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
    print("测试算力链哨兵因子：接入回测引擎")
    print("=" * 60)

    from app.core.openai_chain_sentinel_factor import factor

    df = _make_synthetic_data()
    # 注意：本因子语义为风险预警（正值=风险），此处仅验证可接入回测引擎跑通
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
    print(f"   触发交易次数: {(result_df['trades'] > 0).sum()}")

    assert result_df["equity_curve"].iloc[-1] > 0, "资金曲线应大于 0"

    print("[OK] 回测引擎接入测试通过\n")


def test_consistency_with_research_version():
    print("=" * 60)
    print("测试算力链哨兵因子：与 factor/openai_chain_sentinel.py 打分一致")
    print("=" * 60)

    factor_root = Path(__file__).parent.parent.parent / "factor"
    sys.path.insert(0, str(factor_root))

    from app.core.openai_chain_sentinel_factor import factor as backend_factor
    from openai_chain_sentinel import factor as research_factor

    df = _make_synthetic_data()
    s_backend = backend_factor(df)
    s_research = research_factor(df)

    assert len(s_backend) == len(s_research), "信号长度应一致"
    assert np.allclose(s_backend.values, s_research.values), (
        f"两处实现打分不一致，最大偏差: "
        f"{np.abs(s_backend.values - s_research.values).max()}"
    )

    print(f"   信号序列长度: {len(s_backend)}，两处实现完全一致")
    print("[OK] 一致性测试通过\n")


if __name__ == "__main__":
    test_backend_module_factor()
    test_paste_ready_code_in_sandbox()
    test_factor_with_backtest_engine()
    test_consistency_with_research_version()
    print("全部算力链哨兵因子（后端版）测试通过")
