"""
恐慌性抄底因子（系统兼容版）

可直接复制 PASTE_READY_CODE 到前端 "Python 代码" 模式中使用，
或在后端通过 eval_python_code(df, code) 执行，或导入 factor(df) 使用。

信号规则：
- 对每根 K 线按原 panic_bottom_factors.py 的打分规则计算总分
- 总分 >= 50 时视为恐慌抄底信号，返回信号强度；否则返回 0
"""

import numpy as np
import pandas as pd


def factor(df: pd.DataFrame) -> pd.Series:
    """
    恐慌抄底信号（向量化实现）

    Parameters
    ----------
    df : pd.DataFrame
        包含 open/high/low/close/volume 的标准 OHLCV 数据

    Returns
    -------
    pd.Series
        信号序列，正值表示触发恐慌抄底信号，0 表示无信号
    """
    factors = pd.DataFrame(index=df.index)

    # 1. 基础价格行为
    factors["body"] = df["close"] - df["open"]
    factors["range"] = df["high"] - df["low"]
    factors["lower_shadow"] = np.minimum(df["open"], df["close"]) - df["low"]
    factors["lower_shadow_pct"] = factors["lower_shadow"] / factors["range"] * 100

    # 2. 连续下跌统计
    factors["is_down"] = df["close"] < df["open"]
    factors["consecutive_down"] = (
        factors["is_down"]
        .astype(int)
        .groupby((~factors["is_down"]).astype(int).cumsum())
        .cumsum()
    )

    # 3. 短期跌幅
    factors["return_2"] = df["close"].pct_change(2) * 100

    # 4. 新低判断
    factors["new_low_10"] = df["low"] == df["low"].rolling(10).min()

    # 5. RSI 超卖
    def rsi(prices, period=14):
        delta = prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    factors["rsi_3"] = rsi(df["close"], 3)
    factors["rsi_14"] = rsi(df["close"], 14)

    # 6. 成交量
    factors["volume_ma5"] = df["volume"].rolling(5).mean()
    factors["volume_ratio"] = df["volume"] / factors["volume_ma5"]

    # 7. 破底翻结构
    factors["lower_than_prev"] = df["low"] < df["low"].shift(1)
    factors["close_higher_than_prev"] = df["close"] > df["close"].shift(1)
    factors["break_bottom_reverse"] = (
        factors["lower_than_prev"] & factors["close_higher_than_prev"]
    )

    # 8. 打分（与原 panic_bottom_signal 保持一致）
    score = pd.Series(0.0, index=df.index)

    # 长下影线
    score = score + np.where(
        factors["lower_shadow_pct"] > 40,
        25,
        np.where(factors["lower_shadow_pct"] > 30, 15, 0),
    )

    # 连续下跌
    score = score + np.where(
        factors["consecutive_down"] >= 3,
        20,
        np.where(factors["consecutive_down"] >= 2, 10, 0),
    )

    # 短期超跌
    score = score + np.where(
        factors["return_2"] < -10,
        20,
        np.where(factors["return_2"] < -5, 10, 0),
    )

    # RSI 超卖
    score = score + np.where(
        factors["rsi_3"] < 10,
        15,
        np.where(factors["rsi_14"] < 30, 10, 0),
    )

    # 10 期新低
    score = score + np.where(factors["new_low_10"], 10, 0)

    # 破底翻
    score = score + np.where(factors["break_bottom_reverse"], 10, 0)

    # 放量承接
    score = score + np.where(factors["volume_ratio"] > 1.5, 5, 0)

    # 只有总分 >= 50 才产生信号
    signal = np.where(score >= 50, score, 0)
    return pd.Series(signal, index=df.index)


# 可粘贴到前端 "Python 代码" 输入框的版本（无 import，依赖系统已注入的 np/pd）
PASTE_READY_CODE = """def factor(df):
    factors = pd.DataFrame(index=df.index)

    # 1. 基础价格行为
    factors["body"] = df["close"] - df["open"]
    factors["range"] = df["high"] - df["low"]
    factors["lower_shadow"] = np.minimum(df["open"], df["close"]) - df["low"]
    factors["lower_shadow_pct"] = factors["lower_shadow"] / factors["range"] * 100

    # 2. 连续下跌统计
    factors["is_down"] = df["close"] < df["open"]
    factors["consecutive_down"] = (
        factors["is_down"]
        .astype(int)
        .groupby((~factors["is_down"]).astype(int).cumsum())
        .cumsum()
    )

    # 3. 短期跌幅
    factors["return_2"] = df["close"].pct_change(2) * 100

    # 4. 新低判断
    factors["new_low_10"] = df["low"] == df["low"].rolling(10).min()

    # 5. RSI 超卖
    def rsi(prices, period=14):
        delta = prices.diff()
        gain = delta.where(delta > 0, 0)
        loss = -delta.where(delta < 0, 0)
        avg_gain = gain.rolling(window=period).mean()
        avg_loss = loss.rolling(window=period).mean()
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))

    factors["rsi_3"] = rsi(df["close"], 3)
    factors["rsi_14"] = rsi(df["close"], 14)

    # 6. 成交量
    factors["volume_ma5"] = df["volume"].rolling(5).mean()
    factors["volume_ratio"] = df["volume"] / factors["volume_ma5"]

    # 7. 破底翻结构
    factors["lower_than_prev"] = df["low"] < df["low"].shift(1)
    factors["close_higher_than_prev"] = df["close"] > df["close"].shift(1)
    factors["break_bottom_reverse"] = (
        factors["lower_than_prev"] & factors["close_higher_than_prev"]
    )

    # 8. 打分
    score = pd.Series(0.0, index=df.index)

    score = score + np.where(
        factors["lower_shadow_pct"] > 40,
        25,
        np.where(factors["lower_shadow_pct"] > 30, 15, 0),
    )

    score = score + np.where(
        factors["consecutive_down"] >= 3,
        20,
        np.where(factors["consecutive_down"] >= 2, 10, 0),
    )

    score = score + np.where(
        factors["return_2"] < -10,
        20,
        np.where(factors["return_2"] < -5, 10, 0),
    )

    score = score + np.where(
        factors["rsi_3"] < 10,
        15,
        np.where(factors["rsi_14"] < 30, 10, 0),
    )

    score = score + np.where(factors["new_low_10"], 10, 0)
    score = score + np.where(factors["break_bottom_reverse"], 10, 0)
    score = score + np.where(factors["volume_ratio"] > 1.5, 5, 0)

    signal = np.where(score >= 50, score, 0)
    return pd.Series(signal, index=df.index)
"""
