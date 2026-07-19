import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from app.core.fib_levels import (
    EXTENSION_RATIOS,
    IN_RANGE_RATIOS,
    analyze_fib,
    compute_levels,
    detect_range,
)


def _make_box_data():
    """
    构造底部震荡区间数据（30 根周线）

    第 0-4 根：上涨，第 4 根创出前高 3.0
    第 5 根：暴跌至全局最低价 1.0
    第 6-15 根：区间震荡，高低点均在 [1, 3] 内
    第 16 根：收盘 6.5 > 前高 3.0，突破区间
    之后维持高位
    """
    dates = pd.date_range("2023-01-01", periods=30, freq="7D")
    rows = []
    for i in range(30):
        if i < 4:
            o, h, l, c = 2.0 + i * 0.2, 2.2 + i * 0.2, 1.9 + i * 0.2, 2.1 + i * 0.2
        elif i == 4:
            o, h, l, c = 2.8, 3.0, 2.6, 2.9  # 前高 3.0
        elif i == 5:
            o, h, l, c = 2.9, 2.9, 1.0, 1.5  # 全局最低价 1.0
        elif i <= 15:
            # 区间内震荡，不突破前高
            o, h, l, c = 1.8, 2.4, 1.3, 2.0
        elif i == 16:
            o, h, l, c = 2.0, 6.6, 1.9, 6.5  # 收盘突破前高
        else:
            o, h, l, c = 6.5, 6.8, 6.2, 6.5
        rows.append({"timestamp": dates[i], "open": o, "high": h, "low": l, "close": c, "volume": 1000})
    return pd.DataFrame(rows)


def test_detect_range():
    print("=" * 60)
    print("测试斐波区间判定（前高为 1）")
    print("=" * 60)

    df = _make_box_data()
    info = detect_range(df)

    print(f"   区间: [{info['range_low']}, {info['range_high']}]")
    print(f"   突破时间: {info['breakout_time']}")

    assert info["range_low"] == 1.0, "0 应为全局最低价 1.0"
    assert info["range_high"] == 3.0, f"1 应为最低点之前的前高 3.0，实际 {info['range_high']}"
    assert info["breakout_time"] == df["timestamp"].iloc[16]

    print("[OK] 区间判定测试通过\n")


def test_detect_range_no_prior_high():
    print("=" * 60)
    print("测试斐波区间判定：数据从最低点开始（退化扫描法）")
    print("=" * 60)

    # 第一根就是全局最低价，之后高点被压在 2.0（区间震荡），收盘 3.2 > 1.5×2.0 时突破
    dates = pd.date_range("2023-01-01", periods=10, freq="7D")
    rows = []
    closes = [1.2, 1.5, 1.8, 1.6, 1.9, 2.2, 2.5, 2.8, 3.2, 3.5]
    for i, c in enumerate(closes):
        l = 1.0 if i == 0 else c * 0.9
        h = 2.0 if i < 8 else c * 1.05  # 突破前高点一直被压在 2.0
        rows.append({"timestamp": dates[i], "open": c * 0.95, "high": h, "low": l, "close": c, "volume": 1000})
    df = pd.DataFrame(rows)

    info = detect_range(df)
    print(f"   区间: [{info['range_low']}, {info['range_high']}], 突破: {info['breakout_time']}")

    assert info["range_low"] == 1.0
    assert info["range_high"] == 2.0, f"收盘突破 1.5×2.0 后区间高点应定格 2.0，实际 {info['range_high']}"
    assert info["breakout_time"] == df["timestamp"].iloc[8]

    print("[OK] 退化场景测试通过\n")


def test_compute_levels_math():
    print("=" * 60)
    print("测试斐波价位计算")
    print("=" * 60)

    # 用 SOXL 图的数字验证：0=0.2239, 1=1.26 -> 144 档 ≈ 148.85 + 0.2239
    levels = compute_levels(0.2239, 1.26, current_price=150.0)
    by_ratio = {round(l["ratio"], 3): l for l in levels}

    span = 1.26 - 0.2239
    assert abs(by_ratio[0.236]["price"] - (0.2239 + 0.236 * span)) < 1e-9
    assert abs(by_ratio[144]["price"] - (0.2239 + 144 * span)) < 1e-2  # ≈149.4
    print(f"   144 档价位: {by_ratio[144]['price']:.2f}（图中 148.85+0.22≈149.1，一致）")

    assert [l["ratio"] for l in levels if l["kind"] == "range"] == IN_RANGE_RATIOS
    assert [l["ratio"] for l in levels if l["kind"] == "extension"] == EXTENSION_RATIOS

    print("[OK] 价位计算测试通过\n")


def test_visible_extensions():
    print("=" * 60)
    print("测试扩展档可见性（当前价附近 7 条）")
    print("=" * 60)

    # 区间 [1, 3]，当前价 6.5：下方扩展档 4.236/5，上方 7/11/19/35/67
    levels = compute_levels(1.0, 3.0, current_price=6.5)
    visible_ext = [l for l in levels if l["kind"] == "extension" and l["visible"]]

    print(f"   可见扩展档: {[(l['ratio'], round(l['price'], 2)) for l in visible_ext]}")

    assert len(visible_ext) == 7
    assert [l["ratio"] for l in visible_ext] == [1.618, 2, 3, 5, 8, 13, 21]
    # 区间档位应全部可见
    assert all(l["visible"] for l in levels if l["kind"] == "range")

    # 价格远超全部扩展档时，只显示最近的 7 条（都在下方）
    levels2 = compute_levels(1.0, 3.0, current_price=10000.0)
    visible_ext2 = [l for l in levels2 if l["kind"] == "extension" and l["visible"]]
    assert len(visible_ext2) == 7
    assert visible_ext2[-1]["ratio"] == 377

    print("[OK] 可见性测试通过\n")


def test_analyze_fib_with_override():
    print("=" * 60)
    print("测试手动覆盖区间")
    print("=" * 60)

    df = _make_box_data()
    result = analyze_fib(df, fib_low=0.2239, fib_high=1.26)

    assert result["range"]["range_low"] == 0.2239
    assert result["range"]["range_high"] == 1.26
    assert result["range"]["breakout_time"] is None
    assert result["current_price"] == 6.5

    print("[OK] 手动覆盖测试通过\n")


if __name__ == "__main__":
    test_detect_range()
    test_detect_range_no_prior_high()
    test_compute_levels_math()
    test_visible_extensions()
    test_analyze_fib_with_override()
    print("全部斐波扩展测试通过")
