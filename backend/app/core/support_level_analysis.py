"""
支撑位分析模块

基于 support_level_factor 的策略规则，对一段 K 线做只读分析：
- 计算每根 K 线的动态支撑位与区间高低点
- 识别历史上每次"回踩支撑守住"事件，并向后判定事件结果：
  - bounced：BOUNCE_BARS 根内最高收盘涨幅 >= bounce_threshold（反弹成功）
  - broke：期间先收盘跌破支撑位（支撑破位）
  - pending：后续 K 线不足，无法判定
- 汇总统计：回踩次数、反弹成功率、平均/最大反弹幅度、当前支撑位

同一波持仓期内的连续触发只记为一个事件（以策略持仓信号 0->1 的跳变为事件起点）。
"""

import numpy as np
import pandas as pd

from app.core.support_level_factor import (
    BREAK_TOLERANCE,
    LOOKBACK,
    MIN_RANGE,
    TOUCH_TOLERANCE,
    calc_support,
    factor,
)

DEFAULT_BOUNCE_BARS = 10  # 反弹判定窗口（根）
DEFAULT_BOUNCE_THRESHOLD = 0.05  # 反弹成功阈值（涨幅）


def analyze(
    df: pd.DataFrame,
    lookback: int = LOOKBACK,
    min_range: float = MIN_RANGE,
    touch_tolerance: float = TOUCH_TOLERANCE,
    break_tolerance: float = BREAK_TOLERANCE,
    bounce_bars: int = DEFAULT_BOUNCE_BARS,
    bounce_threshold: float = DEFAULT_BOUNCE_THRESHOLD,
) -> dict:
    """
    支撑位分析

    Parameters
    ----------
    df : pd.DataFrame
        包含 timestamp/open/high/low/close/volume 的标准 OHLCV 数据

    Returns
    -------
    dict
        points: 每根 K 线的支撑位序列（去掉 warmup 的 NaN 段）
        events: 回踩事件列表
        stats: 汇总统计
    """
    df = df.reset_index(drop=True)

    # 支撑序列与区间高低点（参数可覆盖，不直接用 calc_support 的默认值）
    range_high = df["high"].rolling(lookback).max()
    range_low = df["low"].rolling(lookback).min()
    support = (range_high - range_low) / 3 + range_low

    # 复用策略因子得到持仓信号；参数与默认值不同时，现算入场/出场条件
    if (
        lookback == LOOKBACK
        and min_range == MIN_RANGE
        and touch_tolerance == TOUCH_TOLERANCE
        and break_tolerance == BREAK_TOLERANCE
    ):
        pos = factor(df) / 100
    else:
        range_pct = range_high / range_low - 1
        strong = (df["close"] > df["close"].shift(lookback)) & (range_pct >= min_range)
        entry = (
            strong
            & (df["low"] <= support * (1 + touch_tolerance))
            & (df["close"] >= support)
        )
        exit_ = df["close"] < support * (1 - break_tolerance)
        state = pd.Series(np.nan, index=df.index)
        state.loc[exit_] = 0.0
        state.loc[entry] = 1.0
        pos = state.ffill().fillna(0.0)

    # 事件起点：持仓信号 0 -> 1 的跳变
    entry_idx = df.index[(pos > 0) & (pos.shift(1).fillna(0) == 0)]

    events = []
    for i in entry_idx:
        entry_close = df["close"].iloc[i]
        forward = df.iloc[i + 1 : i + 1 + bounce_bars]

        status = "pending"
        max_bounce = 0.0
        if len(forward) > 0:
            # 期间最大收盘涨幅
            max_bounce = float(forward["close"].max() / entry_close - 1)
            # 期间是否先破位：找到第一次收盘跌破支撑的位置
            broke_mask = forward["close"] < support.iloc[forward.index] * (1 - break_tolerance)
            bounce_mask = forward["close"] >= entry_close * (1 + bounce_threshold)
            first_broke = forward.index[broke_mask].min() if broke_mask.any() else None
            first_bounce = forward.index[bounce_mask].min() if bounce_mask.any() else None

            if first_bounce is not None and (first_broke is None or first_bounce < first_broke):
                status = "bounced"
            elif first_broke is not None:
                status = "broke"
            elif len(forward) >= bounce_bars:
                # 窗口走完既没反弹到位也没破位，按未反弹处理
                status = "flat"

        events.append(
            {
                "timestamp": df["timestamp"].iloc[i],
                "support": float(support.iloc[i]),
                "touch_low": float(df["low"].iloc[i]),
                "entry_close": float(entry_close),
                "max_bounce_pct": max_bounce,
                "status": status,
            }
        )

    # 汇总统计
    bounced = sum(1 for e in events if e["status"] == "bounced")
    broke = sum(1 for e in events if e["status"] == "broke")
    judged = [e for e in events if e["status"] in ("bounced", "broke", "flat")]

    current_support = float(support.iloc[-1]) if not np.isnan(support.iloc[-1]) else None
    last_close = float(df["close"].iloc[-1])
    distance_pct = (last_close / current_support - 1) if current_support else None

    stats = {
        "total_touches": len(events),
        "bounced_count": bounced,
        "broke_count": broke,
        "success_rate": (bounced / len(judged)) if judged else None,
        "avg_bounce_pct": float(np.mean([e["max_bounce_pct"] for e in events])) if events else None,
        "max_bounce_pct": max((e["max_bounce_pct"] for e in events), default=None),
        "current_support": current_support,
        "last_close": last_close,
        "distance_to_support_pct": distance_pct,
    }

    # 支撑序列（去掉 warmup NaN 段）
    valid = support.notna()
    points = [
        {
            "timestamp": df["timestamp"].iloc[i],
            "support": float(support.iloc[i]),
            "range_high": float(range_high.iloc[i]),
            "range_low": float(range_low.iloc[i]),
        }
        for i in df.index[valid]
    ]

    return {"points": points, "events": events, "stats": stats}
