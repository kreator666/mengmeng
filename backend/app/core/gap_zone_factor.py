"""
Gap Zone Auto Marker（系统兼容版）

来源：将 docs/signal/tradingview.txt 中的 TradingView Pine Script v5 指标
翻译为 Python 因子，可直接接入后端回测引擎。

Pine 原逻辑要点：
- 只认【趋势延续型】缺口：上跳要求前后两根皆阳线，下跳要求皆阴线；
- 缺口边界可用 "Close to next open" 或 "Wick to wick"；
- 信号在缺口形成当根 K 线产生：上跳 +1，下跳 -1。

回测用法：
- 返回 +1 表示出现上跳缺口（做多信号），-1 表示下跳缺口（做空信号）。
- 若你想做"缺口回补"策略，把信号反向即可：上跳做空、下跳做多。
- 现货市场（market_type=spot）负值会被系统截断为 0，不做空。
"""

import numpy as np
import pandas as pd


# ------------------- 可调参数（与 Pine 输入对应） -------------------
DET_MODE = "Close to next open"       # "Close to next open" 或 "Wick to wick"
MIN_GAP_TICK = 1                      # 最小缺口 tick 数，0 表示不限制
MAX_GAP_TICK = 0                      # 最大缺口 tick 数，0 表示无限制


def _estimate_tick(df: pd.DataFrame) -> float:
    """从 OHLC 估算最小价格单位，作为 tick 的近似。"""
    price_cols = ["open", "high", "low", "close"]
    diffs = df[price_cols].diff().abs().replace(0, np.nan)
    min_diff = diffs.min().min()
    if pd.isna(min_diff) or min_diff == 0:
        return 0.01
    return float(min_diff)


def factor(df: pd.DataFrame) -> pd.Series:
    """
    Gap Zone 信号（向量化实现）

    Parameters
    ----------
    df : pd.DataFrame
        包含 open/high/low/close/volume 的标准 OHLCV 数据

    Returns
    -------
    pd.Series
        信号序列，+1 = 上跳缺口，-1 = 下跳缺口，0 = 无信号
    """
    tick = _estimate_tick(df)
    min_size = MIN_GAP_TICK * tick
    max_size = MAX_GAP_TICK * tick if MAX_GAP_TICK > 0 else 1e18

    prev_bull = df["close"].shift(1) > df["open"].shift(1)
    cur_bull = df["close"] > df["open"]
    prev_bear = df["close"].shift(1) < df["open"].shift(1)
    cur_bear = df["close"] < df["open"]

    if DET_MODE == "Close to next open":
        is_up = prev_bull & cur_bull & (df["open"] > df["close"].shift(1))
        is_dn = prev_bear & cur_bear & (df["open"] < df["close"].shift(1))
    else:  # "Wick to wick"
        is_up = prev_bull & cur_bull & (df["low"] > df["high"].shift(1))
        is_dn = prev_bear & cur_bear & (df["high"] < df["low"].shift(1))

    # 计算缺口大小
    if DET_MODE == "Close to next open":
        lo = np.where(is_up, df["close"].shift(1), np.where(is_dn, df["open"], np.nan))
        hi = np.where(is_up, df["open"], np.where(is_dn, df["close"].shift(1), np.nan))
    else:
        lo = np.where(is_up, df["high"].shift(1), np.where(is_dn, df["low"], np.nan))
        hi = np.where(is_up, df["low"], np.where(is_dn, df["high"].shift(1), np.nan))

    gap_size = hi - lo
    valid = (is_up | is_dn) & (gap_size > 0) & (gap_size >= min_size) & (gap_size <= max_size)

    signal = np.where(valid & is_up, 1.0, np.where(valid & is_dn, -1.0, 0.0))
    return pd.Series(signal, index=df.index)


# 可粘贴到前端 "Python 代码" 输入框的版本（无 import，依赖系统已注入的 np/pd）
PASTE_READY_CODE = """def factor(df):
    # ---- 可调参数 ----
    DET_MODE = "Close to next open"   # "Close to next open" 或 "Wick to wick"
    MIN_GAP_TICK = 1                  # 最小缺口 tick 数，0 表示不限制
    MAX_GAP_TICK = 0                  # 最大缺口 tick 数，0 表示无限制

    # 估算 tick
    price_cols = ["open", "high", "low", "close"]
    diffs = df[price_cols].diff().abs().replace(0, np.nan)
    min_diff = diffs.min().min()
    tick = float(min_diff) if not pd.isna(min_diff) and min_diff > 0 else 0.01

    min_size = MIN_GAP_TICK * tick
    max_size = MAX_GAP_TICK * tick if MAX_GAP_TICK > 0 else 1e18

    prev_bull = df["close"].shift(1) > df["open"].shift(1)
    cur_bull = df["close"] > df["open"]
    prev_bear = df["close"].shift(1) < df["open"].shift(1)
    cur_bear = df["close"] < df["open"]

    is_close = (DET_MODE == "Close to next open")

    # 上跳缺口判定
    up_close = prev_bull & cur_bull & (df["open"] > df["close"].shift(1))
    up_wick = prev_bull & cur_bull & (df["low"] > df["high"].shift(1))
    is_up = is_close * up_close + (1 - is_close) * up_wick

    # 下跳缺口判定
    dn_close = prev_bear & cur_bear & (df["open"] < df["close"].shift(1))
    dn_wick = prev_bear & cur_bear & (df["high"] < df["low"].shift(1))
    is_dn = is_close * dn_close + (1 - is_close) * dn_wick

    # 缺口边界
    lo_close = np.where(is_up, df["close"].shift(1), np.where(is_dn, df["open"], np.nan))
    lo_wick = np.where(is_up, df["high"].shift(1), np.where(is_dn, df["low"], np.nan))
    lo = is_close * lo_close + (1 - is_close) * lo_wick

    hi_close = np.where(is_up, df["open"], np.where(is_dn, df["close"].shift(1), np.nan))
    hi_wick = np.where(is_up, df["low"], np.where(is_dn, df["high"].shift(1), np.nan))
    hi = is_close * hi_close + (1 - is_close) * hi_wick

    gap_size = hi - lo
    valid = (is_up | is_dn) & (gap_size > 0) & (gap_size >= min_size) & (gap_size <= max_size)

    signal = np.where(valid & is_up, 1.0, np.where(valid & is_dn, -1.0, 0.0))
    return pd.Series(signal, index=df.index)
"""
