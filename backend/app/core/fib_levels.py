"""
全局斐波扩展模块

规则（以 SOXL 周线/月线为例验证）：
- 底部震荡区间 [0, 1]：0 = 底部区间震荡最低点（全局最低价），1 = 前高
- 区间自动判定：取全局最低价所在 K 线，1 = 该最低点**之前**的最高价（前高）；
  最低点之后首次收盘站上该前高，视为脱离底部震荡区间
- 例外：若全局最低点就是数据第一根（无更早日 K 线，无法取前高），
  退化为扫描法——从最低点往右维护区间高点，
  收盘 > breakout_factor × 当前区间高点（默认 1.5 倍）时定格
- 斐波价位：price(k) = 区间低点 + k × (区间高点 - 区间低点)
  - 区间内档位：0 / 0.236 / 0.382 / 0.5 / 0.618 / 0.786 / 1
  - 扩展档位：1.618 / 2 / 3 / 5 / 8 / 13 / 21 / 34 / 55 / 89 / 144 / 233 / 377
- 扩展档只显示当前价附近的若干条（默认 7 条：下方最多 3 条 + 上方最多 4 条）
"""

import numpy as np
import pandas as pd

IN_RANGE_RATIOS = [0, 0.236, 0.382, 0.5, 0.618, 0.786, 1.0]
EXTENSION_RATIOS = [1.618, 2, 3, 5, 8, 13, 21, 34, 55, 89, 144, 233, 377]

DEFAULT_BREAKOUT_FACTOR = 1.5
DEFAULT_VISIBLE_EXTENSIONS = 7
BELOW_COUNT = 3  # 当前价下方默认显示的扩展档条数


def detect_range(df: pd.DataFrame, breakout_factor: float = DEFAULT_BREAKOUT_FACTOR) -> dict:
    """
    在周线/月线数据上自动判定底部震荡区间

    0 = 全局最低价；1 = 最低点之前的前高（最高点之前数据中的最高价）。
    若全局最低点就是数据第一根（无前高可取），退化为扫描法：
    从最低点往右维护区间高点，收盘突破 breakout_factor 倍时定格。

    Returns
    -------
    dict
        range_low / range_high / low_time / high_time / breakout_time（无突破为 None）
    """
    lows = df["low"].to_numpy()
    highs = df["high"].to_numpy()
    closes = df["close"].to_numpy()

    i0 = int(np.argmin(lows))
    range_low = float(lows[i0])
    breakout_time = None

    if i0 > 0:
        # 主规则：1 = 最低点之前的前高
        i_high = int(np.argmax(highs[:i0]))
        range_high = float(highs[i_high])
        high_time = df["timestamp"].iloc[i_high]
        # 最低点之后首次收盘站上该前高 = 脱离区间
        for i in range(i0 + 1, len(df)):
            if closes[i] > range_high:
                breakout_time = df["timestamp"].iloc[i]
                break
    else:
        # 退化规则：数据从最低点开始，无前高可取，用扫描法
        box_high = float(highs[i0])
        high_time = df["timestamp"].iloc[i0]
        for i in range(i0 + 1, len(df)):
            if box_high > range_low and closes[i] > breakout_factor * box_high:
                breakout_time = df["timestamp"].iloc[i]
                break
            if highs[i] > box_high:
                box_high = float(highs[i])
                high_time = df["timestamp"].iloc[i]
        range_high = box_high

    return {
        "range_low": range_low,
        "range_high": range_high,
        "low_time": df["timestamp"].iloc[i0],
        "high_time": high_time,
        "breakout_time": breakout_time,
    }


def compute_levels(
    range_low: float,
    range_high: float,
    current_price: float,
    max_visible_extensions: int = DEFAULT_VISIBLE_EXTENSIONS,
) -> list[dict]:
    """
    计算全部斐波价位，并标记扩展档的可见子集（当前价附近）

    Returns
    -------
    list[dict]
        ratio / price / kind（range|extension）/ visible
    """
    span = range_high - range_low
    levels = [
        {"ratio": r, "price": range_low + r * span, "kind": "range", "visible": True}
        for r in IN_RANGE_RATIOS
    ]

    ext = [
        {"ratio": r, "price": range_low + r * span, "kind": "extension", "visible": False}
        for r in EXTENSION_RATIOS
    ]
    below = [l for l in ext if l["price"] < current_price]
    above = [l for l in ext if l["price"] >= current_price]

    sel_below = below[-BELOW_COUNT:]
    sel_above = above[: max_visible_extensions - len(sel_below)]
    # 上方不足时，名额让给下方
    shortage = max_visible_extensions - len(sel_below) - len(sel_above)
    if shortage > 0:
        sel_below = below[: -BELOW_COUNT][-shortage:] + sel_below

    for l in sel_below + sel_above:
        l["visible"] = True

    return levels + ext


def analyze_fib(
    df: pd.DataFrame,
    breakout_factor: float = DEFAULT_BREAKOUT_FACTOR,
    fib_low: float | None = None,
    fib_high: float | None = None,
    max_visible_extensions: int = DEFAULT_VISIBLE_EXTENSIONS,
) -> dict:
    """
    斐波扩展分析：区间判定 + 档位计算

    fib_low / fib_high 同时提供时跳过自动判定（手动覆盖区间）
    """
    current_price = float(df["close"].iloc[-1])

    if fib_low is not None and fib_high is not None:
        range_info = {
            "range_low": float(fib_low),
            "range_high": float(fib_high),
            "low_time": None,
            "high_time": None,
            "breakout_time": None,
        }
    else:
        range_info = detect_range(df, breakout_factor)

    levels = compute_levels(
        range_info["range_low"],
        range_info["range_high"],
        current_price,
        max_visible_extensions,
    )

    return {"range": range_info, "levels": levels, "current_price": current_price}
