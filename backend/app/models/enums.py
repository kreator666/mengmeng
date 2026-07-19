from enum import Enum


class Provider(str, Enum):
    """行情数据源"""

    GATEIO = "gateio"
    BINANCE = "binance"
    US_STOCK = "us_stock"


class MarketType(str, Enum):
    SPOT = "spot"
    FUTURES_USDT = "futures_usdt"
    FUTURES_BTC = "futures_btc"


class Interval(str, Enum):
    ONE_MINUTE = "1m"
    FIVE_MINUTES = "5m"
    FIFTEEN_MINUTES = "15m"
    THIRTY_MINUTES = "30m"
    ONE_HOUR = "1h"
    TWO_HOURS = "2h"
    FOUR_HOURS = "4h"
    EIGHT_HOURS = "8h"
    ONE_DAY = "1d"
    THREE_DAYS = "3d"
    ONE_WEEK = "7d"
    ONE_MONTH = "30d"
    THREE_MONTHS = "3M"


class FactorMode(str, Enum):
    FORMULA = "formula"
    PYTHON = "python"


class PositionMode(str, Enum):
    FIXED_AMOUNT = "fixed_amount"
    FIXED_RATIO = "fixed_ratio"
    KELLY = "kelly"
    VOLATILITY_TARGET = "volatility_target"
