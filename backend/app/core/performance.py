from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd


def extract_trades(df: pd.DataFrame) -> list[dict[str, Any]]:
    """从仓位变化中提取交易记录"""
    trades = []
    position = df["position"]
    price = df["close"]
    timestamp = df["timestamp"]

    entry_time = None
    entry_price = 0.0
    side = None

    for i in range(len(df)):
        current_pos = position.iloc[i]
        prev_pos = position.iloc[i - 1] if i > 0 else 0.0

        if prev_pos == 0 and current_pos > 0:
            entry_time = timestamp.iloc[i]
            entry_price = price.iloc[i]
            side = "long"
        elif prev_pos == 0 and current_pos < 0:
            entry_time = timestamp.iloc[i]
            entry_price = price.iloc[i]
            side = "short"
        elif prev_pos != 0 and current_pos == 0 and entry_time is not None:
            exit_time = timestamp.iloc[i]
            exit_price = price.iloc[i]
            if side == "long":
                pnl = (exit_price - entry_price) / entry_price
            else:
                pnl = (entry_price - exit_price) / entry_price
            trades.append({
                "entry_time": entry_time,
                "exit_time": exit_time,
                "side": side,
                "entry_price": float(entry_price),
                "exit_price": float(exit_price),
                "pnl": float(pnl),
                "return_pct": float(pnl),
            })
            entry_time = None

    return trades


def calculate_performance(df: pd.DataFrame, initial_capital: float = 10000.0) -> dict[str, Any]:
    """
    计算绩效指标
    """
    returns = df["net_returns"].dropna()
    equity = df["equity_curve"]

    if len(returns) == 0 or equity.empty:
        return _empty_summary()

    total_return = equity.iloc[-1] / initial_capital - 1
    n_days = max((df["timestamp"].iloc[-1] - df["timestamp"].iloc[0]).days, 1)
    annualized_return = (1 + total_return) ** (365 / n_days) - 1

    # 最大回撤
    cummax = equity.cummax()
    drawdown = (equity - cummax) / cummax
    max_drawdown = drawdown.min()
    max_drawdown_duration = _max_drawdown_duration(drawdown)

    # 波动率
    volatility = returns.std() * np.sqrt(365)
    downside_returns = returns[returns < 0]
    downside_volatility = downside_returns.std() * np.sqrt(365) if len(downside_returns) > 0 else 0.0

    # 风险调整收益
    risk_free = 0.0
    sharpe = (annualized_return - risk_free) / volatility if volatility != 0 else 0.0
    sortino = (annualized_return - risk_free) / downside_volatility if downside_volatility != 0 else 0.0
    calmar = annualized_return / abs(max_drawdown) if max_drawdown != 0 else 0.0

    # 交易统计
    trades = extract_trades(df)
    total_trades = len(trades)
    win_count = sum(1 for t in trades if t["pnl"] > 0)
    win_rate = win_count / total_trades if total_trades > 0 else 0.0
    profit_factor = _profit_factor(trades)
    avg_trade_return = np.mean([t["return_pct"] for t in trades]) if trades else 0.0

    # Alpha
    buy_hold_return = df["close"].iloc[-1] / df["close"].iloc[0] - 1
    buy_hold_annualized = (1 + buy_hold_return) ** (365 / n_days) - 1
    alpha = annualized_return - buy_hold_annualized

    return {
        "total_return": float(total_return),
        "annualized_return": float(annualized_return),
        "max_drawdown": float(max_drawdown),
        "max_drawdown_duration": int(max_drawdown_duration),
        "volatility": float(volatility),
        "downside_volatility": float(downside_volatility),
        "sharpe_ratio": float(sharpe),
        "sortino_ratio": float(sortino),
        "calmar_ratio": float(calmar),
        "total_trades": int(total_trades),
        "win_rate": float(win_rate),
        "profit_factor": float(profit_factor),
        "avg_trade_return": float(avg_trade_return),
        "alpha": float(alpha),
    }


def _empty_summary() -> dict[str, Any]:
    return {
        "total_return": 0.0,
        "annualized_return": 0.0,
        "max_drawdown": 0.0,
        "max_drawdown_duration": 0,
        "volatility": 0.0,
        "downside_volatility": 0.0,
        "sharpe_ratio": 0.0,
        "sortino_ratio": 0.0,
        "calmar_ratio": 0.0,
        "total_trades": 0,
        "win_rate": 0.0,
        "profit_factor": 0.0,
        "avg_trade_return": 0.0,
        "alpha": 0.0,
    }


def _max_drawdown_duration(drawdown: pd.Series) -> int:
    """计算最大回撤持续天数"""
    duration = 0
    max_duration = 0
    in_drawdown = False
    for value in drawdown:
        if value < 0:
            if not in_drawdown:
                duration = 1
                in_drawdown = True
            else:
                duration += 1
        else:
            in_drawdown = False
            duration = 0
        max_duration = max(max_duration, duration)
    return max_duration


def _profit_factor(trades: list[dict[str, Any]]) -> float:
    gross_profit = sum(t["pnl"] for t in trades if t["pnl"] > 0)
    gross_loss = abs(sum(t["pnl"] for t in trades if t["pnl"] < 0))
    return gross_profit / gross_loss if gross_loss != 0 else 0.0
