from typing import Any

import numpy as np
import pandas as pd

from app.core.cost_model import CostModel
from app.core.position_manager import PositionManager
from app.models.enums import PositionMode


def _apply_sl_tp(
    df: pd.DataFrame,
    target_position: pd.Series,
    stop_loss: float,
    take_profit: float,
    max_holding_bars: int,
) -> tuple[pd.Series, pd.Series]:
    """
    根据止损/止盈/最大持仓周期调整仓位。

    逻辑：
    - 入场价为触发当根 K 线的收盘价
    - 一旦开仓，仅由止损/止盈/最大持仓周期决定出场
    - 若触发止损/止盈，以触发价作为出场价
    - max_holding_bars 为 0 表示不限制持仓周期
    - 出场后需等信号归零再重新入场，避免连续触发

    返回
    ------
    position : pd.Series
        每根 K 线的实际仓位（1=持仓，0=空仓）
    exit_price : pd.Series
        平仓当根 K 线的出场价，未平仓时为 NaN
    """
    position = pd.Series(0.0, index=df.index)
    exit_price = pd.Series(np.nan, index=df.index)

    in_trade = False
    entry_price = 0.0
    entry_idx = 0
    wait_signal_reset = False  # 出场后等待信号归零

    for i in range(len(df)):
        if not in_trade:
            if wait_signal_reset:
                if target_position.iloc[i] == 0:
                    wait_signal_reset = False
                position.iloc[i] = 0.0
                continue

            if target_position.iloc[i] > 0:
                in_trade = True
                entry_price = float(df["close"].iloc[i])
                entry_idx = i

        if in_trade:
            bars_held = i - entry_idx
            stop_price = entry_price * (1 - stop_loss) if stop_loss > 0 else -np.inf
            take_price = entry_price * (1 + take_profit) if take_profit > 0 else np.inf

            # 使用极小容差避免浮点精度问题（如 100 * 1.1 = 110.00000000000001）
            eps = 1e-9
            hit_stop = stop_loss > 0 and float(df["low"].iloc[i]) <= stop_price + eps
            hit_take = take_profit > 0 and float(df["high"].iloc[i]) >= take_price - eps
            hit_time = max_holding_bars > 0 and bars_held >= max_holding_bars

            if hit_stop or hit_take or hit_time:
                price = float(df["close"].iloc[i])
                if hit_stop:
                    price = stop_price
                elif hit_take:
                    price = take_price
                exit_price.iloc[i] = round(price, 10)
                position.iloc[i] = 1.0
                in_trade = False
                wait_signal_reset = True
            else:
                position.iloc[i] = 1.0
        else:
            position.iloc[i] = 0.0

    return position, exit_price


def _calculate_strategy_returns(df: pd.DataFrame) -> pd.Series:
    """
    根据仓位和出场价计算策略收益率。
    """
    returns = pd.Series(0.0, index=df.index)
    prev_close = df["close"].shift(1)

    for i in range(1, len(df)):
        if df["position"].iloc[i] == 0 and df["position"].iloc[i - 1] == 0:
            continue

        if not pd.isna(df["exit_price"].iloc[i]):
            # 本 K 线平仓：收益从上一根收盘价到出场价
            returns.iloc[i] = (df["exit_price"].iloc[i] - prev_close.iloc[i]) / prev_close.iloc[i]
        else:
            # 普通持仓 K 线：收益从上一根收盘价到本根收盘价
            returns.iloc[i] = (df["close"].iloc[i] - prev_close.iloc[i]) / prev_close.iloc[i]

    return returns


def vectorized_backtest(
    df: pd.DataFrame,
    signal: pd.Series,
    initial_capital: float = 10000.0,
    position_mode: PositionMode = PositionMode.FIXED_RATIO,
    position_ratio: float = 0.95,
    cost_model: CostModel | None = None,
    allow_short: bool = False,
    stop_loss: float = 0.0,
    take_profit: float = 0.0,
    max_holding_bars: int = 0,
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
    stop_loss : float
        止损比例，例如 0.05 表示跌 5% 止损；0 表示不启用
    take_profit : float
        止盈比例，例如 0.1 表示涨 10% 止盈；0 表示不启用
    max_holding_bars : int
        最大持仓 K 线数，0 表示不限制

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

    # 3. 应用止损止盈逻辑
    use_sl_tp = stop_loss > 0 or take_profit > 0 or max_holding_bars > 0
    if use_sl_tp:
        df["position"], df["exit_price"] = _apply_sl_tp(
            df,
            df["target_position"],
            stop_loss,
            take_profit,
            max_holding_bars,
        )
    else:
        df["position"] = df["target_position"].shift(1).fillna(0)
        df["exit_price"] = np.nan

    # 4. 计算策略收益
    if use_sl_tp:
        df["strategy_returns"] = _calculate_strategy_returns(df)
    else:
        df["strategy_returns"] = df["position"] * df["returns"]

    # 5. 计算交易成本
    df["trades"] = df["position"].diff().abs()
    df["cost"] = df["trades"] * cost_model.total_cost_per_trade()

    # 6. 扣除成本后的收益
    df["net_returns"] = df["strategy_returns"] - df["cost"]

    # 7. 计算资金曲线
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
    stop_loss: float = 0.0,
    take_profit: float = 0.0,
    max_holding_bars: int = 0,
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
        stop_loss=stop_loss,
        take_profit=take_profit,
        max_holding_bars=max_holding_bars,
    )
