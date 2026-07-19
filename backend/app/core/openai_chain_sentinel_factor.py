"""
OpenAI 算力链风险哨兵因子（系统兼容版）

背景与研究框架：research/OpenAI算力绑定_思维框架与投资指导.md
思路：OpenAI 循环交易链上个股的单日暴跌/集体破位是整条链的传染起点。

可直接复制 PASTE_READY_CODE 到前端 "Python 代码" 模式中使用，
或在后端通过 eval_python_code(df, code) 执行，或导入 factor(df) 使用。

信号规则：
- 对每根 K 线按 factor/openai_chain_sentinel.py 的打分规则计算链风险总分
- 总分 >= 50 时视为链风险预警信号，返回信号强度（0-100）；否则返回 0
- 注意：语义与做多因子相反，正值 = 风险预警，可用作减仓/对冲/过滤信号
"""

import numpy as np
import pandas as pd


def factor(df: pd.DataFrame) -> pd.Series:
    """
    链风险预警信号（向量化实现）

    Parameters
    ----------
    df : pd.DataFrame
        包含 open/high/low/close/volume 的标准 OHLCV 数据

    Returns
    -------
    pd.Series
        信号序列，正值表示触发链风险预警（0-100），0 表示无信号
    """
    factors = pd.DataFrame(index=df.index)

    # 1. 跌幅（链上个股单日暴跌是传染起点）
    factors["return_1"] = df["close"].pct_change(1) * 100
    factors["return_5"] = df["close"].pct_change(5) * 100

    # 2. 趋势破位
    factors["ma60"] = df["close"].rolling(60).mean()
    factors["ma120"] = df["close"].rolling(120).mean()
    factors["below_ma60"] = df["close"] < factors["ma60"]
    factors["below_ma120"] = df["close"] < factors["ma120"]

    # 3. 高点回撤（120 日）
    factors["high_120"] = df["close"].rolling(120).max()
    factors["drawdown_120"] = (df["close"] / factors["high_120"] - 1) * 100

    # 4. 放量下跌（恐慌出逃）
    factors["volume_ma10"] = df["volume"].rolling(10).mean()
    factors["volume_ratio"] = df["volume"] / factors["volume_ma10"]
    factors["is_down"] = df["close"] < df["open"]

    # 5. 打分（与 factor/openai_chain_sentinel.py 的 chain_risk_signal 保持一致）
    score = pd.Series(0.0, index=df.index)

    # 单日暴跌
    score = score + np.where(
        factors["return_1"] <= -7,
        40,
        np.where(factors["return_1"] <= -5, 25, np.where(factors["return_1"] <= -3, 10, 0)),
    )

    # 五日跌幅
    score = score + np.where(
        factors["return_5"] <= -15,
        30,
        np.where(factors["return_5"] <= -10, 20, np.where(factors["return_5"] <= -5, 10, 0)),
    )

    # 趋势破位
    score = score + np.where(
        factors["below_ma120"], 15, np.where(factors["below_ma60"], 10, 0)
    )

    # 高点深度回撤
    score = score + np.where(
        factors["drawdown_120"] <= -30,
        15,
        np.where(factors["drawdown_120"] <= -20, 10, 0),
    )

    # 放量下跌
    score = score + np.where(
        (factors["volume_ratio"] > 2) & factors["is_down"], 10, 0
    )

    # 总分封顶 100，>= 50 才产生信号
    score = np.minimum(score, 100)
    signal = np.where(score >= 50, score, 0)
    return pd.Series(signal, index=df.index)


# 可粘贴到前端 "Python 代码" 输入框的版本（无 import，依赖系统已注入的 np/pd）
PASTE_READY_CODE = """def factor(df):
    factors = pd.DataFrame(index=df.index)

    # 1. 跌幅（链上个股单日暴跌是传染起点）
    factors["return_1"] = df["close"].pct_change(1) * 100
    factors["return_5"] = df["close"].pct_change(5) * 100

    # 2. 趋势破位
    factors["ma60"] = df["close"].rolling(60).mean()
    factors["ma120"] = df["close"].rolling(120).mean()
    factors["below_ma60"] = df["close"] < factors["ma60"]
    factors["below_ma120"] = df["close"] < factors["ma120"]

    # 3. 高点回撤（120 日）
    factors["high_120"] = df["close"].rolling(120).max()
    factors["drawdown_120"] = (df["close"] / factors["high_120"] - 1) * 100

    # 4. 放量下跌（恐慌出逃）
    factors["volume_ma10"] = df["volume"].rolling(10).mean()
    factors["volume_ratio"] = df["volume"] / factors["volume_ma10"]
    factors["is_down"] = df["close"] < df["open"]

    # 5. 打分
    score = pd.Series(0.0, index=df.index)

    score = score + np.where(
        factors["return_1"] <= -7,
        40,
        np.where(factors["return_1"] <= -5, 25, np.where(factors["return_1"] <= -3, 10, 0)),
    )

    score = score + np.where(
        factors["return_5"] <= -15,
        30,
        np.where(factors["return_5"] <= -10, 20, np.where(factors["return_5"] <= -5, 10, 0)),
    )

    score = score + np.where(
        factors["below_ma120"], 15, np.where(factors["below_ma60"], 10, 0)
    )

    score = score + np.where(
        factors["drawdown_120"] <= -30,
        15,
        np.where(factors["drawdown_120"] <= -20, 10, 0),
    )

    score = score + np.where(
        (factors["volume_ratio"] > 2) & factors["is_down"], 10, 0
    )

    score = np.minimum(score, 100)
    signal = np.where(score >= 50, score, 0)
    return pd.Series(signal, index=df.index)
"""
