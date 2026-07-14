from typing import Any

import numpy as np
import pandas as pd

from app.core.cost_model import CostModel
from app.core.position_manager import PositionManager
from app.models.enums import PositionMode


def vectorized_backtest(
    df: pd.DataFrame,
    signal: pd.Series,
    initial_capital: float = 10000.0,
    position_mode: PositionMode = PositionMode.FIXED_RATIO,
    position_ratio: float = 0.95,
    cost_model: CostModel | None = None,
    allow_short: bool = False,
) -> pd.DataFrame:
    """
    向量化回测核心

    Parameters
    ----------
    df : pd.DataFrame
        包含 OHLCV 的标准化 K 线数据
    signal : pd.Series
        信号序列，正值做多，负值做空，0 空仓
    initial_capital : float
        初始资金
    position_mode : PositionMode
        仓位模式
    position_ratio : float
        仓位比例（固定比例模式使用）
    cost_model : CostModel
        成本模型
    allow_short : bool
        是否允许做空（现货默认不允许）

    Returns
    -------
    pd.DataFrame
        包含回测结果的 DataFrame
    """
    df = df.copy().reset_index(drop=True)
    cost_model = cost_model or CostModel()

    # 1. 计算收益率
    df["returns"] = df["close"].pct_change()

    # 2. 信号标准化与位移（避免未来函数）
    raw_signal = signal.reindex(df.index).fillna(0)
    # 将信号映射到仓位：正数 -> 1（做多），负数 -> -1（做空），0 -> 0
    df["target_position"] = np.where(raw_signal > 0, 1, np.where(raw_signal < 0, -1, 0))
    if not allow_short:
        df["target_position"] = df["target_position"].clip(lower=0)

    df["position"] = df["target_position"].shift(1).fillna(0)

    # 3. 计算策略收益（向量化）
    df["strategy_returns"] = df["position"] * df["returns"]

    # 4. 计算交易成本
    df["trades"] = df["position"].diff().abs()
    df["cost"] = df["trades"] * cost_model.total_cost_per_trade()

    # 5. 扣除成本后的收益
    df["net_returns"] = df["strategy_returns"] - df["cost"]

    # 6. 计算资金曲线
    df["equity_curve"] = initial_capital * (1 + df["net_returns"]).cumprod()

    return df


def backtest_with_position_sizing(
    df: pd.DataFrame,
    signal: pd.Series,
    initial_capital: float = 10000.0,
    position_mode: PositionMode = PositionMode.FIXED_RATIO,
    position_ratio: float = 0.95,
    cost_model: CostModel | None = None,
    allow_short: bool = False,
) -> pd.DataFrame:
    """
    带仓位管理的向量化回测（保留扩展接口）
    """
    # 当前版本使用固定仓位比例，后续可扩展凯利公式、波动率目标等
    return vectorized_backtest(
        df=df,
        signal=signal,
        initial_capital=initial_capital,
        position_mode=position_mode,
        position_ratio=position_ratio,
        cost_model=cost_model,
        allow_short=allow_short,
    )
