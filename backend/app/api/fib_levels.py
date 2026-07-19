from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.core.fib_levels import (
    DEFAULT_BREAKOUT_FACTOR,
    DEFAULT_VISIBLE_EXTENSIONS,
    analyze_fib,
)
from app.data.cache_manager import CacheManager
from app.models.enums import Interval, MarketType, Provider
from app.models.schemas import FibLevelsResponse

router = APIRouter(tags=["fib-levels"])

# 斐波区间只支持周线/月线确认
ALLOWED_INTERVALS = {Interval.ONE_WEEK, Interval.ONE_MONTH}


@router.get("/api/fib-levels", response_model=FibLevelsResponse)
async def get_fib_levels(
    symbol: str = Query(..., description="交易对，如 BTC_USDT"),
    interval: Interval = Query(default=Interval.ONE_WEEK, description="区间确认周期：7d（周线）或 30d（月线）"),
    market_type: MarketType = Query(default=MarketType.SPOT),
    provider: Provider = Query(default=Provider.GATEIO, description="行情数据源"),
    from_date: str = Query(default="1990-01-01", alias="from", description="开始日期 YYYY-MM-DD"),
    to_date: str | None = Query(default=None, alias="to", description="结束日期 YYYY-MM-DD，默认今天"),
    breakout_factor: float = Query(default=DEFAULT_BREAKOUT_FACTOR, gt=1.0, description="脱离区间判定倍数"),
    fib_low: float | None = Query(default=None, description="手动覆盖区间低点（需与 fib_high 同时提供）"),
    fib_high: float | None = Query(default=None, description="手动覆盖区间高点"),
    max_visible_extensions: int = Query(default=DEFAULT_VISIBLE_EXTENSIONS, ge=1, le=20, description="当前价附近显示的扩展档条数"),
):
    """全局斐波扩展：底部震荡区间（0-1）+ 区间档位 + 扩展档位"""
    if interval not in ALLOWED_INTERVALS:
        raise HTTPException(status_code=400, detail="斐波区间只支持周线(7d)或月线(30d)确认")

    if (fib_low is None) != (fib_high is None):
        raise HTTPException(status_code=400, detail="fib_low 与 fib_high 需同时提供")

    if fib_low is not None and fib_high is not None and fib_low >= fib_high:
        raise HTTPException(status_code=400, detail="fib_low 必须小于 fib_high")

    try:
        start = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=None)
        if to_date:
            end = datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=None)
        else:
            end = datetime.utcnow()
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD")

    if start >= end:
        raise HTTPException(status_code=400, detail="开始日期必须早于结束日期")

    manager = CacheManager(provider=provider)
    try:
        df = await manager.get_klines(symbol.upper(), interval, market_type, start, end)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"数据获取失败: {str(e)}")
    finally:
        await manager.close()

    if df.empty:
        raise HTTPException(status_code=404, detail="该时间段无 K 线数据")

    result = analyze_fib(
        df,
        breakout_factor=breakout_factor,
        fib_low=fib_low,
        fib_high=fib_high,
        max_visible_extensions=max_visible_extensions,
    )

    return FibLevelsResponse(
        symbol=symbol.upper(),
        interval=interval.value,
        provider=provider.value,
        **result,
    )
