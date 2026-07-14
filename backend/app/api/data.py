from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from app.data.cache_manager import CacheManager
from app.models.enums import Interval, MarketType
from app.models.schemas import KlineResponse

router = APIRouter(tags=["data"])


@router.get("/api/data/klines")
async def get_klines(
    symbol: str = Query(..., description="交易对，如 BTC_USDT"),
    interval: Interval = Query(default=Interval.ONE_HOUR),
    market_type: MarketType = Query(default=MarketType.SPOT),
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

    manager = CacheManager()
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
):
    """获取交易对列表"""
    manager = CacheManager()
    try:
        if market_type == MarketType.SPOT:
            raw = await manager.client.get_spot_symbols()
            symbols = [
                {
                    "symbol": item.get("id"),
                    "market_type": market_type.value,
                    "base": item.get("base"),
                    "quote": item.get("quote"),
                }
                for item in raw
                if item.get("trade_status") == "tradable"
            ]
        else:
            settle = "usdt" if market_type == MarketType.FUTURES_USDT else "btc"
            raw = await manager.client.get_futures_contracts(settle)
            symbols = [
                {
                    "symbol": item.get("name"),
                    "market_type": market_type.value,
                    "base": item.get("base"),
                    "quote": item.get("quote"),
                }
                for item in raw
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取交易对失败: {str(e)}")
    finally:
        await manager.close()

    return symbols
