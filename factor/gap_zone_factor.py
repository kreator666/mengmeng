# Gap Zone Auto Marker - 可复用代码
# 来源：docs/signal/tradingview.txt 的 Pine Script v5 翻译
# 说明：仅识别趋势延续型缺口，上跳要求前后两根皆阳线，下跳要求皆阴线。

import numpy as np
import pandas as pd


def calculate_gap_zone_signal(df, det_mode="Close to next open", min_gap_tick=1, max_gap_tick=0):
    """
    计算 Gap Zone 信号。

    Parameters
    ----------
    df : pd.DataFrame
        OHLCV 数据
    det_mode : str
        "Close to next open" 或 "Wick to wick"
    min_gap_tick : int
        最小缺口 tick 数
    max_gap_tick : int
        最大缺口 tick 数，0 表示无限制

    Returns
    -------
    pd.Series
        +1 = 上跳缺口，-1 = 下跳缺口，0 = 无信号
    """
    price_cols = ["open", "high", "low", "close"]
    diffs = df[price_cols].diff().abs().replace(0, np.nan)
    min_diff = diffs.min().min()
    tick = float(min_diff) if not pd.isna(min_diff) and min_diff > 0 else 0.01

    min_size = min_gap_tick * tick
    max_size = max_gap_tick * tick if max_gap_tick > 0 else 1e18

    prev_bull = df["close"].shift(1) > df["open"].shift(1)
    cur_bull = df["close"] > df["open"]
    prev_bear = df["close"].shift(1) < df["open"].shift(1)
    cur_bear = df["close"] < df["open"]

    if det_mode == "Close to next open":
        is_up = prev_bull & cur_bull & (df["open"] > df["close"].shift(1))
        is_dn = prev_bear & cur_bear & (df["open"] < df["close"].shift(1))
    else:
        is_up = prev_bull & cur_bull & (df["low"] > df["high"].shift(1))
        is_dn = prev_bear & cur_bear & (df["high"] < df["low"].shift(1))

    if det_mode == "Close to next open":
        lo = np.where(is_up, df["close"].shift(1), np.where(is_dn, df["open"], np.nan))
        hi = np.where(is_up, df["open"], np.where(is_dn, df["close"].shift(1), np.nan))
    else:
        lo = np.where(is_up, df["high"].shift(1), np.where(is_dn, df["low"], np.nan))
        hi = np.where(is_up, df["low"], np.where(is_dn, df["high"].shift(1), np.nan))

    gap_size = hi - lo
    valid = (is_up | is_dn) & (gap_size > 0) & (gap_size >= min_size) & (gap_size <= max_size)

    signal = np.where(valid & is_up, 1.0, np.where(valid & is_dn, -1.0, 0.0))
    return pd.Series(signal, index=df.index)


def factor(df):
    """
    系统回测接口：接收 OHLCV DataFrame，返回信号 Series
    正值 = 上跳缺口（做多），负值 = 下跳缺口（做空），0 = 无信号
    """
    return calculate_gap_zone_signal(df)


# 使用示例
# signal = factor(df)
