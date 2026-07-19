from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.core.support_level_analysis import (
    DEFAULT_BOUNCE_BARS,
    DEFAULT_BOUNCE_THRESHOLD,
    analyze,
)
from app.core.support_level_factor import (
    BREAK_TOLERANCE,
    LOOKBACK,
    MIN_RANGE,
    TOUCH_TOLERANCE,
)
from app.data.cache_manager import CacheManager
from app.models.enums import Interval, MarketType, Provider
from app.models.schemas import SupportLevelAnalyzeResponse

router = APIRouter(tags=["support-level"])


@router.get("/api/support-level/analyze", response_model=SupportLevelAnalyzeResponse)
async def analyze_support_level(
    symbol: str = Query(..., description="交易对，如 BTC_USDT"),
    interval: Interval = Query(default=Interval.ONE_HOUR),
    market_type: MarketType = Query(default=MarketType.SPOT),
    provider: Provider = Query(default=Provider.GATEIO, description="行情数据源"),
    from_date: str = Query(..., alias="from", description="开始日期 YYYY-MM-DD"),
    to_date: str = Query(..., alias="to", description="结束日期 YYYY-MM-DD"),
    lookback: int = Query(default=LOOKBACK, ge=5, le=500, description="区间窗口（K 线数）"),
    min_range: float = Query(default=MIN_RANGE, ge=0.0, description="区间最小涨幅"),
    touch_tolerance: float = Query(default=TOUCH_TOLERANCE, ge=0.0, description="回踩容忍度"),
    break_tolerance: float = Query(default=BREAK_TOLERANCE, ge=0.0, description="破位确认幅度"),
    bounce_bars: int = Query(default=DEFAULT_BOUNCE_BARS, ge=1, le=200, description="反弹判定窗口（根）"),
    bounce_threshold: float = Query(default=DEFAULT_BOUNCE_THRESHOLD, gt=0.0, description="反弹成功阈值"),
):
    """支撑位分析：动态支撑序列 + 历史回踩事件 + 反弹统计"""
    try:
        start = datetime.strptime(from_date, "%Y-%m-%d").replace(tzinfo=None)
        end = datetime.strptime(to_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=None)
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

    result = analyze(
        df,
        lookback=lookback,
        min_range=min_range,
        touch_tolerance=touch_tolerance,
        break_tolerance=break_tolerance,
        bounce_bars=bounce_bars,
        bounce_threshold=bounce_threshold,
    )

    return SupportLevelAnalyzeResponse(
        symbol=symbol.upper(),
        interval=interval.value,
        provider=provider.value,
        **result,
    )
