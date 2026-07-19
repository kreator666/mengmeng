from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.data.cache_manager import CacheManager
from app.models.enums import Interval, MarketType, Provider
from app.models.schemas import KlineResponse

router = APIRouter(tags=["data"])

# 交易对列表内存缓存（Gate 全量列表接口很慢，~50s；列表变化不频繁，缓存 1 小时）
_symbols_cache: dict[str, tuple[float, list]] = {}
SYMBOLS_CACHE_TTL = 3600


@router.get("/api/data/klines")
async def get_klines(
    symbol: str = Query(..., description="交易对，如 BTC_USDT"),
    interval: Interval = Query(default=Interval.ONE_HOUR),
    market_type: MarketType = Query(default=MarketType.SPOT),
    provider: Provider = Query(default=Provider.GATEIO, description="行情数据源"),
    from_date: str = Query(..., alias="from", description="开始日期 YYYY-MM-DD"),
    to_date: str = Query(..., alias="to", description="结束日期 YYYY-MM-DD"),
):
    """获取 K 线数据"""
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
        return []

    records = df[["timestamp", "open", "high", "low", "close", "volume"]].to_dict("records")
    return [KlineResponse(**r) for r in records]


@router.get("/api/symbols")
async def get_symbols(
    market_type: MarketType = Query(default=MarketType.SPOT),
    provider: Provider = Query(default=Provider.GATEIO, description="行情数据源"),
):
    """获取交易对列表（1 小时内存缓存）"""
    import time

    cache_key = f"{provider.value}:{market_type.value}"
    cached = _symbols_cache.get(cache_key)
    if cached and time.time() - cached[0] < SYMBOLS_CACHE_TTL:
        return cached[1]

    manager = CacheManager(provider=provider)
    try:
        if market_type == MarketType.SPOT:
            symbols = await manager.client.get_spot_symbols()
        else:
            settle = "usdt" if market_type == MarketType.FUTURES_USDT else "btc"
            symbols = await manager.client.get_futures_symbols(settle=settle)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取交易对失败: {str(e)}")
    finally:
        await manager.close()

    _symbols_cache[cache_key] = (time.time(), symbols)
    return symbols
