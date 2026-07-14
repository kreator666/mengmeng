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
from app.data.factor_store import FactorStore
from app.models.schemas import CustomFactorCreate, CustomFactorUpdate, FactorEvalRequest

router = APIRouter(prefix="/api/factor", tags=["factor"])
custom_factor_router = APIRouter(prefix="/api/factors", tags=["custom-factor"])


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


# 自定义因子 CRUD（使用 /api/factors 复数路径，与 /api/factor/* 内置因子接口区分）
_factor_store = FactorStore()


@router.get("/library")
async def get_factor_library():
    """获取完整因子库（内置因子 + 自定义因子）"""
    return {
        "builtins": get_builtin_factors(),
        "custom": [f.__dict__ for f in _factor_store.list()],
    }


@custom_factor_router.get("")
async def list_custom_factors():
    """获取自定义因子列表"""
    factors = _factor_store.list()
    return {"factors": [f.__dict__ for f in factors]}


@custom_factor_router.get("/{factor_id}")
async def get_custom_factor(factor_id: str):
    """获取单个自定义因子详情"""
    factor = _factor_store.get(factor_id)
    if not factor:
        raise HTTPException(status_code=404, detail="因子不存在")
    return factor.__dict__


@custom_factor_router.post("")
async def create_custom_factor(request: CustomFactorCreate):
    """创建自定义因子"""
    if not request.name or not request.name.strip():
        raise HTTPException(status_code=400, detail="因子名称不能为空")
    if not request.code or not request.code.strip():
        raise HTTPException(status_code=400, detail="因子代码不能为空")

    mode = request.mode.strip().lower()
    if mode not in ("formula", "python"):
        raise HTTPException(status_code=400, detail="mode 必须是 formula 或 python")

    factor = _factor_store.create(
        name=request.name.strip(),
        category=request.category.strip() or "自定义",
        description=request.description.strip(),
        mode=mode,
        code=request.code.strip(),
    )
    return factor.__dict__


@custom_factor_router.put("/{factor_id}")
async def update_custom_factor(factor_id: str, request: CustomFactorUpdate):
    """更新自定义因子"""
    update_data = request.model_dump(exclude_unset=True)
    if not update_data:
        raise HTTPException(status_code=400, detail="没有需要更新的字段")

    if "mode" in update_data:
        update_data["mode"] = update_data["mode"].strip().lower()
        if update_data["mode"] not in ("formula", "python"):
            raise HTTPException(status_code=400, detail="mode 必须是 formula 或 python")

    factor = _factor_store.update(factor_id, **update_data)
    if not factor:
        raise HTTPException(status_code=404, detail="因子不存在")
    return factor.__dict__


@custom_factor_router.delete("/{factor_id}")
async def delete_custom_factor(factor_id: str):
    """删除自定义因子"""
    success = _factor_store.delete(factor_id)
    if not success:
        raise HTTPException(status_code=404, detail="因子不存在")
    return {"message": "删除成功"}
