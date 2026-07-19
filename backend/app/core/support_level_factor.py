"""
三分之一支撑位策略（系统兼容版）

规则来源：
    支撑位 = (区间高点 - 区间低点) / 3 + 区间低点
    强势的股票回调时这个支撑位破不了，回踩支撑位附近是接货位置。

信号规则：
- 用 LOOKBACK 根 K 线定义"区间"，计算区间高点/低点和支撑位
- 强势过滤：当前收盘价高于 LOOKBACK 根之前（区间维度处于上涨），
  且区间涨幅 >= MIN_RANGE（确保有一波像样的拉升）
- 入场：盘中最低价回踩到支撑位附近（TOUCH_TOLERANCE 以内），
  且收盘价守在支撑位之上（支撑没破）
- 出场：收盘价跌破支撑位（BREAK_TOLERANCE 确认）→ 支撑失效，离场

可直接复制 PASTE_READY_CODE 到前端 "Python 代码" 模式中使用，
或在后端通过 eval_python_code(df, code) 执行，或导入 factor(df) 使用。
"""

import numpy as np
import pandas as pd

# 策略参数
LOOKBACK = 60  # 区间窗口（K 线数）
MIN_RANGE = 0.10  # 区间最小涨幅（高点/低点 - 1），过滤横盘
TOUCH_TOLERANCE = 0.03  # 回踩容忍度：低点触及支撑位上方 3% 以内视为回踩
BREAK_TOLERANCE = 0.01  # 破位确认：收盘低于支撑位 1% 以上视为跌破


def calc_support(df: pd.DataFrame, lookback: int = LOOKBACK) -> pd.Series:
    """计算每根 K 线对应的支撑位序列：(区间高点-区间低点)/3 + 区间低点"""
    range_high = df["high"].rolling(lookback).max()
    range_low = df["low"].rolling(lookback).min()
    return (range_high - range_low) / 3 + range_low


def factor(df: pd.DataFrame) -> pd.Series:
    """
    三分之一支撑位信号（向量化实现）

    Parameters
    ----------
    df : pd.DataFrame
        包含 open/high/low/close/volume 的标准 OHLCV 数据

    Returns
    -------
    pd.Series
        信号序列，持仓期间为 100，空仓为 0
    """
    range_high = df["high"].rolling(LOOKBACK).max()
    range_low = df["low"].rolling(LOOKBACK).min()
    support = (range_high - range_low) / 3 + range_low
    range_pct = range_high / range_low - 1

    # 强势过滤：区间维度处于上涨，且区间涨幅足够
    strong = (df["close"] > df["close"].shift(LOOKBACK)) & (range_pct >= MIN_RANGE)

    # 入场：回踩支撑位附近，且收盘守住支撑
    entry = (
        strong
        & (df["low"] <= support * (1 + TOUCH_TOLERANCE))
        & (df["close"] >= support)
    )

    # 出场：收盘跌破支撑位
    exit_ = df["close"] < support * (1 - BREAK_TOLERANCE)

    # 入场后持有，直到破位离场（向量化状态机）
    pos = pd.Series(np.nan, index=df.index)
    pos.loc[exit_] = 0.0
    pos.loc[entry] = 1.0
    pos = pos.ffill().fillna(0.0)

    return pos * 100


# 可粘贴到前端 "Python 代码" 输入框的版本（无 import，依赖系统已注入的 np/pd）
PASTE_READY_CODE = """def factor(df):
    LOOKBACK = 60        # 区间窗口（K 线数）
    MIN_RANGE = 0.10     # 区间最小涨幅，过滤横盘
    TOUCH_TOLERANCE = 0.03   # 回踩容忍度：低点触及支撑位上方 3% 以内
    BREAK_TOLERANCE = 0.01   # 破位确认：收盘低于支撑位 1% 以上

    range_high = df["high"].rolling(LOOKBACK).max()
    range_low = df["low"].rolling(LOOKBACK).min()
    # 支撑位 = (区间高点 - 区间低点) / 3 + 区间低点
    support = (range_high - range_low) / 3 + range_low
    range_pct = range_high / range_low - 1

    # 强势过滤：区间维度处于上涨，且区间涨幅足够
    strong = (df["close"] > df["close"].shift(LOOKBACK)) & (range_pct >= MIN_RANGE)

    # 入场：回踩支撑位附近，且收盘守住支撑
    entry = (
        strong
        & (df["low"] <= support * (1 + TOUCH_TOLERANCE))
        & (df["close"] >= support)
    )

    # 出场：收盘跌破支撑位
    exit_ = df["close"] < support * (1 - BREAK_TOLERANCE)

    # 入场后持有，直到破位离场
    pos = pd.Series(np.nan, index=df.index)
    pos.loc[exit_] = 0.0
    pos.loc[entry] = 1.0
    pos = pos.ffill().fillna(0.0)

    return pos * 100
"""
