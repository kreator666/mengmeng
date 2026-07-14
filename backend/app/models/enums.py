from enum import Enum


class MarketType(str, Enum):
    SPOT = "spot"
    FUTURES_USDT = "futures_usdt"
    FUTURES_BTC = "futures_btc"


class Interval(str, Enum):
    ONE_HOUR = "1h"
    FOUR_HOURS = "4h"
    ONE_DAY = "1d"


class FactorMode(str, Enum):
    FORMULA = "formula"
    PYTHON = "python"


class PositionMode(str, Enum):
    FIXED_AMOUNT = "fixed_amount"
    FIXED_RATIO = "fixed_ratio"
    KELLY = "kelly"
    VOLATILITY_TARGET = "volatility_target"
