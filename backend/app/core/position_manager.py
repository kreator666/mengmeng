import pandas as pd


class PositionManager:
    """仓位管理"""

    @staticmethod
    def fixed_amount(capital: float, price: float, amount: float) -> float:
        return amount / price

    @staticmethod
    def fixed_ratio(capital: float, price: float, ratio: float) -> float:
        return (capital * ratio) / price

    @staticmethod
    def kelly(win_rate: float, avg_win: float, avg_loss: float) -> float:
        """凯利公式：f* = (p*b - q) / b"""
        if avg_loss == 0:
            return 0.0
        b = avg_win / avg_loss
        q = 1 - win_rate
        f = (win_rate * b - q) / b
        return max(0.0, min(f, 1.0))

    @staticmethod
    def volatility_target(capital: float, price: float, atr: float, target_vol: float = 0.02) -> float:
        """波动率目标仓位"""
        if atr == 0 or price == 0:
            return 0.0
        return (capital * target_vol) / (atr * price)
