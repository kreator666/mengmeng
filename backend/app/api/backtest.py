import math
import uuid
from datetime import datetime

from fastapi import APIRouter, HTTPException

from app.core.backtest_engine import vectorized_backtest
from app.core.cost_model import CostModel
from app.core.factor_engine import eval_formula, eval_python_code
from app.core.performance import calculate_performance, extract_trades
from app.data.cache_manager import CacheManager
from app.data.result_store import BacktestResultStore
from app.models.enums import MarketType, PositionMode
from app.models.schemas import BacktestRequest, BacktestResult, BacktestSummary, TradeRecord

router = APIRouter(prefix="/api/backtest", tags=["backtest"])

_result_store = BacktestResultStore()


@router.post("/run")
async def run_backtest(request: BacktestRequest):
    """执行回测"""
    strategy = request.strategy
    data_params = request.data

    symbol = data_params.symbol.upper()
    interval = data_params.interval
    market_type = data_params.market_type
    start = datetime.combine(data_params.from_date, datetime.min.time())
    end = datetime.combine(data_params.to_date, datetime.max.time())

    factor_mode = strategy.get("factor_mode", "formula")
    expression = strategy.get("factor_expression", "")
    code = strategy.get("factor_code", "")
    position_mode = PositionMode(strategy.get("position_mode", "fixed_ratio"))
    position_ratio = strategy.get("position_ratio", 0.95)
    initial_capital = strategy.get("initial_capital", 10000.0)
    fee_rate = strategy.get("fee_rate", 0.002)
    slippage = strategy.get("slippage", 0.0005)
    stop_loss = strategy.get("stop_loss", 0.0)
    take_profit = strategy.get("take_profit", 0.0)
    max_holding_bars = strategy.get("max_holding_bars", 0)

    manager = CacheManager()
    try:
        df = await manager.get_klines(symbol, interval, market_type, start, end)
    except Exception as e:
        import traceback
        error_detail = f"数据获取失败: {type(e).__name__}: {str(e)}"
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=error_detail)
    finally:
        await manager.close()

    if df.empty:
        raise HTTPException(status_code=400, detail="未获取到 K 线数据")

    # 计算信号
    try:
        if factor_mode == "formula":
            signal = eval_formula(df, expression)
        else:
            signal = eval_python_code(df, code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"因子计算失败: {str(e)}")

    # 执行回测
    cost_model = CostModel(fee_rate=fee_rate, slippage=slippage)
    allow_short = market_type != MarketType.SPOT
    result_df = vectorized_backtest(
        df=df,
        signal=signal,
        initial_capital=initial_capital,
        position_mode=position_mode,
        position_ratio=position_ratio,
        cost_model=cost_model,
        allow_short=allow_short,
        stop_loss=stop_loss,
        take_profit=take_profit,
        max_holding_bars=max_holding_bars,
    )

    # 计算绩效与交易记录
    summary_dict = calculate_performance(result_df, initial_capital)
    trades = extract_trades(result_df)

    # 构建返回数据
    bt_id = str(uuid.uuid4())

    equity_curve = result_df[["timestamp", "equity_curve"]].rename(columns={"equity_curve": "equity"}).to_dict("records")
    equity_curve = [{"timestamp": r["timestamp"].isoformat(), "equity": r["equity"]} for r in equity_curve]

    cummax = result_df["equity_curve"].cummax()
    drawdown = (result_df["equity_curve"] - cummax) / cummax
    drawdown_series = [
        {"timestamp": ts.isoformat(), "drawdown": dd}
        for ts, dd in zip(result_df["timestamp"], drawdown)
    ]

    trade_records = []
    for t in trades:
        trade_records.append(TradeRecord(**t).model_dump())

    result = BacktestResult(
        id=bt_id,
        symbol=symbol,
        interval=interval,
        market_type=market_type.value,
        from_date=data_params.from_date,
        to_date=data_params.to_date,
        summary=BacktestSummary(**summary_dict),
        equity_curve=equity_curve,
        drawdown_series=drawdown_series,
        trades=trade_records,
    )

    def _clean_value(v):
        if isinstance(v, float):
            if math.isnan(v) or math.isinf(v):
                return 0.0
        return v

    def _clean_dict(d):
        return {k: _clean_value(v) for k, v in d.items()}

    # 返回给前端的 Pydantic 模型（FastAPI 自动序列化）
    # 持久化存储需要 JSON 可序列化的字典
    result_dict = result.model_dump(mode="json")
    result_dict["summary"] = _clean_dict(result_dict["summary"])
    result_dict["equity_curve"] = [{k: _clean_value(v) for k, v in r.items()} for r in result_dict["equity_curve"]]
    result_dict["drawdown_series"] = [{k: _clean_value(v) for k, v in r.items()} for r in result_dict["drawdown_series"]]
    result_dict["trades"] = [{k: _clean_value(v) for k, v in t.items()} for t in result_dict["trades"]]

    _result_store.save(bt_id, result_dict)
    return result


@router.get("")
async def list_backtests(limit: int = 100):
    """获取历史回测结果列表"""
    results = _result_store.list(limit=limit)
    return {"results": results}


@router.get("/{id}")
async def get_backtest(id: str):
    """获取回测结果"""
    result = _result_store.get(id)
    if not result:
        raise HTTPException(status_code=404, detail="回测结果不存在")
    return result


@router.get("/{id}/equity")
async def get_equity(id: str):
    """获取资金曲线"""
    result = _result_store.get(id)
    if not result:
        raise HTTPException(status_code=404, detail="回测结果不存在")
    return result["equity_curve"]


@router.get("/{id}/trades")
async def get_trades(id: str):
    """获取交易记录"""
    result = _result_store.get(id)
    if not result:
        raise HTTPException(status_code=404, detail="回测结果不存在")
    return result["trades"]
