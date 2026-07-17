from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

import pandas as pd

from app.models.enums import Interval, MarketType


class MarketDataClient(ABC):
    """行情数据源抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """provider 名称，如 binance / gateio"""

    @abstractmethod
    async def fetch_klines(
        self,
        symbol: str,
        interval: Interval,
        market_type: MarketType,
        start_time: datetime,
        end_time: datetime,
    ) -> pd.DataFrame:
        """拉取 K 线，返回统一 OHLCV DataFrame"""

    @abstractmethod
    async def get_spot_symbols(self) -> list[dict[str, Any]]:
        """获取现货交易对列表，返回统一格式 SymbolInfo 列表"""

    @abstractmethod
    async def get_futures_symbols(self, settle: str = "usdt") -> list[dict[str, Any]]:
        """获取合约交易对列表，返回统一格式 SymbolInfo 列表"""

    async def close(self):
        """释放连接，子类按需实现"""
        pass
