import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "factor"))

import numpy as np
import pandas as pd

from openai_chain_sentinel import (
    factor,
    calculate_chain_risk_factors,
    chain_risk_signal,
    calculate_chain_factors,
    chain_regime,
)


def _make_df(daily_returns, start="2025-01-01", base=100.0, volume=1000.0):
    """由日收益率序列构造 OHLCV DataFrame"""
    n = len(daily_returns)
    dates = pd.bdate_range(start, periods=n)
    closes = base * np.cumprod(1 + np.array(daily_returns) / 100)
    data = []
    prev = base
    for i in range(n):
        close = closes[i]
        open_p = prev
        high = max(open_p, close) * 1.005
        low = min(open_p, close) * 0.995
        vol = volume * (3 if daily_returns[i] <= -7 else 1)
        data.append({"timestamp": dates[i], "open": open_p, "high": high,
                     "low": low, "close": close, "volume": vol})
        prev = close
    return pd.DataFrame(data)


def test_single_stock_risk_factor():
    print("=" * 60)
    print("测试链风险哨兵：单标的暴跌触发")
    print("=" * 60)

    # 140 天稳步上涨 + 最后 3 天连续暴跌（-3%, -6%, -8%）
    rets = [0.4] * 140 + [0.0] * 2 + [-3.0, -6.0, -8.0]
    df = _make_df(rets)

    signal = factor(df)
    positive_count = (signal > 0).sum()

    factors = calculate_chain_risk_factors(df)
    _, score, reasons = chain_risk_signal(factors, factors.index[-1])

    print(f"   K 线数量: {len(df)}")
    print(f"   触发信号数量: {positive_count}")
    print(f"   末日风险评分: {score}，理由: {reasons}")

    assert positive_count > 0, "暴跌日应触发链风险信号"
    assert signal.max() >= 50, "信号强度应 >= 50"
    assert len(signal) == len(df), "信号长度应与 K 线一致"

    print("[OK] 单标的测试通过\n")


def _make_price_map(member_rets, qqq_rets):
    price_map = {sym: _make_df(rets) for sym, rets in member_rets.items()}
    price_map["QQQ"] = _make_df(qqq_rets)
    return price_map


def test_chain_regime_a():
    print("=" * 60)
    print("测试链风险哨兵：情景A 良性循环")
    print("=" * 60)

    members = {"NVDA": [0.35] * 120, "ORCL": [0.30] * 120, "AMD": [0.40] * 120, "AVGO": [0.30] * 120}
    price_map = _make_price_map(members, [0.10] * 120)

    chain = calculate_chain_factors(price_map, members=list(members))
    regime, score, reasons = chain_regime(chain, chain.index[-1])

    print(f"   判级: {regime}，风险评分: {score}，理由: {reasons}")
    assert regime == "A", f"稳定跑赢应判为情景A，实际 {regime}"

    print("[OK] 情景A 测试通过\n")


def test_chain_regime_b():
    print("=" * 60)
    print("测试链风险哨兵：情景B 高位消化")
    print("=" * 60)

    # 成员缓慢阴跌（无暴跌、无传染），基准走平
    members = {"NVDA": [-0.15] * 120, "ORCL": [-0.10] * 120, "AMD": [-0.20] * 120, "AVGO": [-0.10] * 120}
    price_map = _make_price_map(members, [0.0] * 120)

    chain = calculate_chain_factors(price_map, members=list(members))
    regime, score, reasons = chain_regime(chain, chain.index[-1])

    print(f"   判级: {regime}，风险评分: {score}，理由: {reasons}")
    assert regime == "B", f"阴跌消化应判为情景B，实际 {regime}"

    print("[OK] 情景B 测试通过\n")


def test_chain_regime_c():
    print("=" * 60)
    print("测试链风险哨兵：情景C 循环破裂预警")
    print("=" * 60)

    # 100 天上涨后，最后 3 天全体成员连续暴跌（传染）
    members = {
        sym: [0.3] * 100 + [-8.0, -8.0, -8.0]
        for sym in ["NVDA", "ORCL", "AMD", "AVGO"]
    }
    price_map = _make_price_map(members, [0.1] * 100 + [-1.0, -1.0, -1.0])

    chain = calculate_chain_factors(price_map, members=list(members))
    regime, score, reasons = chain_regime(chain, chain.index[-1])

    print(f"   判级: {regime}，风险评分: {score}，理由: {reasons}")
    print(f"   近5日成员暴跌次数: {chain['crash_count_5d'].iloc[-1]:.0f}")
    assert regime == "C", f"集体暴跌应判为情景C，实际 {regime}"
    assert chain["crash_count_5d"].iloc[-1] >= 3, "应统计到传染性暴跌"

    print("[OK] 情景C 测试通过\n")


if __name__ == "__main__":
    test_single_stock_risk_factor()
    test_chain_regime_a()
    test_chain_regime_b()
    test_chain_regime_c()
    print("全部算力链哨兵因子测试通过")
