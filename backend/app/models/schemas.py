from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, field_validator

from .enums import FactorMode, Interval, MarketType, PositionMode


class KlineRequest(BaseModel):
    model_config = {"populate_by_name": True}

    symbol: str = Field(..., description="交易对，如 BTC_USDT")
    interval: Interval = Field(default=Interval.ONE_HOUR)
    market_type: MarketType = Field(default=MarketType.SPOT)
    from_date: date = Field(..., alias="from")
    to_date: date = Field(..., alias="to")

    @field_validator("symbol")
    @classmethod
    def uppercase_symbol(cls, v: str) -> str:
        return v.strip().upper()


class KlineResponse(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


class SymbolInfo(BaseModel):
    symbol: str
    market_type: MarketType
    base: str
    quote: str


class FactorEvalRequest(BaseModel):
    mode: FactorMode
    expression: Optional[str] = None
    code: Optional[str] = None
    symbol: str = Field(default="BTC_USDT")
    interval: Interval = Field(default=Interval.ONE_HOUR)
    market_type: MarketType = Field(default=MarketType.SPOT)
    from_date: date = Field(default=date(2024, 1, 1), alias="from")
    to_date: date = Field(default=date(2024, 12, 31), alias="to")


class BacktestRequest(BaseModel):
    strategy: dict[str, Any]
    data: KlineRequest


class BacktestSummary(BaseModel):
    total_return: float
    annualized_return: float
    max_drawdown: float
    max_drawdown_duration: int
    volatility: float
    downside_volatility: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    total_trades: int
    win_rate: float
    profit_factor: float
    avg_trade_return: float
    alpha: float


class TradeRecord(BaseModel):
    entry_time: datetime
    exit_time: datetime
    side: Literal["long", "short"]
    entry_price: float
    exit_price: float
    pnl: float
    return_pct: float


class BacktestResult(BaseModel):
    id: str
    summary: BacktestSummary
    equity_curve: list[dict[str, Any]]
    drawdown_series: list[dict[str, Any]]
    trades: list[TradeRecord]


class StrategyConfig(BaseModel):
    name: str
    description: Optional[str] = None
    factor_mode: FactorMode
    factor_expression: Optional[str] = None
    factor_code: Optional[str] = None
    position_mode: PositionMode = PositionMode.FIXED_RATIO
    position_ratio: float = Field(default=0.95, ge=0.0, le=1.0)
    initial_capital: float = Field(default=10000.0, gt=0.0)
    fee_rate: float = Field(default=0.002, ge=0.0)
    slippage: float = Field(default=0.0005, ge=0.0)


class StrategyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    config: StrategyConfig


class StrategyResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    config: StrategyConfig
    created_at: datetime
    updated_at: datetime
