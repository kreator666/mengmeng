from datetime import datetime
from typing import Any

import pandas as pd
from fastapi import APIRouter, HTTPException

from app.core.factor_engine import (
    build_builtin_namespace,
    calculate_ic,
    calculate_rolling_ic,
    eval_formula,
    eval_python_code,
    get_builtin_factors,
    signal_to_position,
)
from app.data.cache_manager import CacheManager
from app.models.schemas import FactorEvalRequest

router = APIRouter(prefix="/api/factor", tags=["factor"])


async def _load_data(params: FactorEvalRequest):
    """加载 K 线数据"""
    start = datetime.combine(params.from_date, datetime.min.time())
    end = datetime.combine(params.to_date, datetime.max.time())
    manager = CacheManager()
    try:
        df = await manager.get_klines(params.symbol, params.interval, params.market_type, start, end)
    finally:
        await manager.close()
    return df


@router.post("/eval")
async def eval_factor(request: FactorEvalRequest):
    """预览因子信号"""
    df = await _load_data(request)
    if df.empty:
        raise HTTPException(status_code=400, detail="未获取到 K 线数据")

    try:
        if request.mode.value == "formula":
            signal = eval_formula(df, request.expression or "")
        else:
            signal = eval_python_code(df, request.code or "")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"因子计算失败: {str(e)}")

    allow_short = request.market_type.value != "spot"
    position = signal_to_position(signal, allow_short=allow_short)

    records = []
    for ts, val, pos in zip(df["timestamp"], signal, position):
        records.append({
            "timestamp": ts.isoformat(),
            "signal": float(val) if not isinstance(val, bool) else (1.0 if val else 0.0),
            "position": float(pos),
        })

    # IC 分析
    returns = df["close"].pct_change()
    ic = calculate_ic(signal, returns)
    rolling_ic = calculate_rolling_ic(signal, returns)
    rolling_ic_records = [
        {"timestamp": ts.isoformat(), "ic": float(val) if not pd.isna(val) else None}
        for ts, val in zip(df["timestamp"], rolling_ic)
    ]

    return {
        "signal": records,
        "ic": ic,
        "rolling_ic": rolling_ic_records,
    }


@router.get("/builtins")
async def get_builtins():
    """获取内置因子列表"""
    return {"factors": get_builtin_factors()}


@router.post("/ic")
async def calculate_factor_ic(request: FactorEvalRequest):
    """计算因子 IC"""
    df = await _load_data(request)
    if df.empty:
        raise HTTPException(status_code=400, detail="未获取到 K 线数据")

    try:
        if request.mode.value == "formula":
            signal = eval_formula(df, request.expression or "")
        else:
            signal = eval_python_code(df, request.code or "")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"因子计算失败: {str(e)}")

    returns = df["close"].pct_change()
    ic = calculate_ic(signal, returns)
    rolling_ic = calculate_rolling_ic(signal, returns)

    return {
        "ic": ic,
        "rolling_ic": [
            {"timestamp": ts.isoformat(), "ic": float(val) if not pd.isna(val) else None}
            for ts, val in zip(df["timestamp"], rolling_ic)
        ],
    }
