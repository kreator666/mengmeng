"""
Markethon 比赛系统代理路由。

将 design/game.md 中描述的 https://markethon.fit:19371 接口代理到
本系统的 /api/markethon/* 路径下，便于前端同源访问并统一保管登录态。
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.factor_engine import get_builtin_factors
from app.data.factor_store import FactorStore
from app.data.markethon_factor_map_store import MarkethonFactorMapStore
from app.services.markethon_client import MarkethonClient, MarkethonError, get_markethon_client

router = APIRouter(prefix="/api/markethon", tags=["markethon"])


def _handle_markethon_error(e: MarkethonError) -> None:
    """把 Markethon 客户端异常转译为 FastAPI HTTPException。"""
    raise HTTPException(status_code=e.status_code or 500, detail=e.detail)


# ---------------------------------------------------------------------------
# 认证
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str = Field(..., description="用户名，新用户自动注册")
    password: str = Field(..., description="密码，至少 6 位")


class LoginResponse(BaseModel):
    access_token: str = Field(..., description="Bearer token")
    token_type: str = Field(default="bearer", description="token 类型")


@router.post("/auth/login", response_model=LoginResponse)
async def login(body: LoginRequest):
    """登录或注册 Markethon 账号，成功后后端缓存 token。"""
    client = get_markethon_client()
    try:
        data = await client.login(username=body.username, password=body.password)
    except MarkethonError as e:
        _handle_markethon_error(e)
    return LoginResponse(
        access_token=data.get("access_token") or data.get("token") or "",
        token_type=data.get("token_type", "bearer"),
    )


# ---------------------------------------------------------------------------
# 系统
# ---------------------------------------------------------------------------


@router.get("/health")
async def get_health() -> dict[str, Any]:
    """Markethon 服务健康检查（无需认证）。"""
    client = get_markethon_client()
    try:
        return await client.get_health()
    except MarkethonError as e:
        _handle_markethon_error(e)


@router.get("/status")
async def get_status() -> dict[str, Any]:
    """Markethon 数据加载状态。"""
    client = get_markethon_client()
    try:
        return await client.get_status()
    except MarkethonError as e:
        _handle_markethon_error(e)


# ---------------------------------------------------------------------------
# 数据
# ---------------------------------------------------------------------------


class LoadDataRequest(BaseModel):
    limit: int = Field(default=500, description="全市场取前 N 只；0 表示全部")
    symbols: list[str] | None = Field(default=None, description="显式股票列表")
    universe: str | list[str] | None = Field(default=None, description="品种列表，如 ['IF', 'IC']")
    start: str = Field(default="2021-08-21", description="起始日")
    end: str = Field(default="2026-08-20", description="截止日")
    alpha360: bool = Field(default=False, description="是否同时缓存 Alpha360")


@router.get("/data/symbols")
async def list_symbols(limit: int = Query(default=50, ge=1)) -> dict[str, Any]:
    """列出全市场 A 股代码。"""
    client = get_markethon_client()
    try:
        return await client.list_symbols(limit=limit)
    except MarkethonError as e:
        _handle_markethon_error(e)


@router.post("/data/load")
async def load_data(body: LoadDataRequest) -> dict[str, Any]:
    """加载 Markethon 日线数据与预计算因子。"""
    client = get_markethon_client()
    try:
        return await client.load_data(
            limit=body.limit,
            symbols=body.symbols,
            universe=body.universe,
            start=body.start,
            end=body.end,
            alpha360=body.alpha360,
        )
    except MarkethonError as e:
        _handle_markethon_error(e)


# ---------------------------------------------------------------------------
# 因子
# ---------------------------------------------------------------------------


class DefineFactorRequest(BaseModel):
    name: str = Field(..., description="因子名")
    expression: str = Field(..., description="qlib 表达式，≤1000 字符")


class EvaluateFactorsRequest(BaseModel):
    names: list[str] = Field(..., description="因子名列表")
    periods: list[int] | None = Field(default=None, description="前瞻收益持有期")
    quantiles: int = Field(default=5, ge=2, description="分组数")
    top_n: int = Field(default=50, ge=1, description="返回条数")


class EvaluateAllRequest(BaseModel):
    factor_set: str = Field(default="alpha158", description="alpha158 / alpha360 / all")
    periods: list[int] | None = Field(default=None, description="前瞻收益持有期")
    quantiles: int = Field(default=5, ge=2, description="分组数")
    top_n: int = Field(default=50, ge=1, description="返回条数")


class EvaluateJobRequest(BaseModel):
    names: list[str] | None = Field(default=None, description="因子名列表；null 表示批量评估")
    factor_set: str = Field(default="alpha158", description="alpha158 / alpha360 / all")
    periods: list[int] | None = Field(default=None, description="前瞻收益持有期")
    quantiles: int = Field(default=5, ge=2, description="分组数")


@router.get("/factors")
async def list_factors() -> dict[str, Any]:
    """列出可用因子。"""
    client = get_markethon_client()
    try:
        return await client.list_factors()
    except MarkethonError as e:
        _handle_markethon_error(e)


@router.post("/factors/define")
async def define_factor(body: DefineFactorRequest) -> dict[str, Any]:
    """注册 qlib 表达式因子。"""
    client = get_markethon_client()
    try:
        return await client.define_factor(name=body.name, expression=body.expression)
    except MarkethonError as e:
        _handle_markethon_error(e)


@router.post("/factors/evaluate")
async def evaluate_factors(body: EvaluateFactorsRequest) -> dict[str, Any]:
    """对指定因子做 IC 评估。"""
    client = get_markethon_client()
    try:
        return await client.evaluate_factors(
            names=body.names,
            periods=body.periods,
            quantiles=body.quantiles,
            top_n=body.top_n,
        )
    except MarkethonError as e:
        _handle_markethon_error(e)


@router.post("/factors/evaluate_all")
async def evaluate_all(body: EvaluateAllRequest) -> dict[str, Any]:
    """批量评估指定因子集。"""
    client = get_markethon_client()
    try:
        return await client.evaluate_all(
            factor_set=body.factor_set,
            periods=body.periods,
            quantiles=body.quantiles,
            top_n=body.top_n,
        )
    except MarkethonError as e:
        _handle_markethon_error(e)


@router.post("/jobs/evaluate")
async def create_evaluate_job(body: EvaluateJobRequest) -> dict[str, Any]:
    """启动异步 IC 评估任务。"""
    client = get_markethon_client()
    try:
        return await client.evaluate_job(
            names=body.names,
            factor_set=body.factor_set,
            periods=body.periods,
            quantiles=body.quantiles,
        )
    except MarkethonError as e:
        _handle_markethon_error(e)


@router.get("/jobs/{job_id}")
async def get_evaluate_job(job_id: str) -> dict[str, Any]:
    """查询异步 IC 评估任务进度与结果。"""
    client = get_markethon_client()
    try:
        return await client.get_job(job_id=job_id)
    except MarkethonError as e:
        _handle_markethon_error(e)


# ---------------------------------------------------------------------------
# 回测
# ---------------------------------------------------------------------------


class BacktestQuantileRequest(BaseModel):
    names: list[str] = Field(..., description="参与合成的因子")
    weights: dict[str, float] | None = Field(default=None, description="因子权重")
    long_short: bool = Field(default=True, description="个股多头 − 指数空头 / 纯多头")
    periods: int = Field(default=5, ge=1, description="调仓周期")
    quantiles: int = Field(default=5, ge=2, description="分组数")
    benchmark: str | None = Field(default=None, description="空头指数：IC/IF/IH/IM")


class WalkForwardRequest(BaseModel):
    names: list[str] = Field(..., description="候选因子池")
    train_months: int = Field(default=12, ge=1, description="训练窗口月数")
    test_months: int = Field(default=3, ge=1, description="测试窗口月数")
    step_months: int = Field(default=3, ge=1, description="滚动步长")
    long_short: bool = Field(default=True, description="个股多头 − 指数空头 / 纯多头")
    quantiles: int = Field(default=5, ge=2, description="分组数")
    rebalance_periods: int = Field(default=5, ge=1, description="调仓周期")
    category_counts: dict[str, int] | None = Field(default=None, description="各类按 |ICIR| 选取数量")
    uncategorized_count: int = Field(default=5, ge=0, description="未分类因子的选取数")
    selection_method: str = Field(default="legacy", description="legacy / robust")
    min_abs_icir: float = Field(default=0.10, description="最低 |ICIR| 及半样本稳定分数")
    min_abs_ic: float = Field(default=0.005, description="最低 |IC|")
    corr_threshold: float = Field(default=0.75, description="因子截面秩相关剔除阈值")
    weight_shrinkage: float = Field(default=0.50, description="ICIR 权重向等权收缩强度")
    benchmark: str | None = Field(default=None, description="空头指数：IC/IF/IH/IM")
    submit_score: bool = Field(default=False, description="是否保存本次标准分")


@router.post("/backtest/quantile")
async def backtest_quantile(body: BacktestQuantileRequest) -> dict[str, Any]:
    """多因子合成打分 + 分组回测。"""
    client = get_markethon_client()
    try:
        return await client.backtest_quantile(
            names=body.names,
            weights=body.weights,
            long_short=body.long_short,
            periods=body.periods,
            quantiles=body.quantiles,
            benchmark=body.benchmark,
        )
    except MarkethonError as e:
        _handle_markethon_error(e)


@router.post("/backtest/walk_forward")
async def walk_forward(body: WalkForwardRequest) -> dict[str, Any]:
    """滚动验证回测。"""
    client = get_markethon_client()
    try:
        return await client.walk_forward(
            names=body.names,
            train_months=body.train_months,
            test_months=body.test_months,
            step_months=body.step_months,
            long_short=body.long_short,
            quantiles=body.quantiles,
            rebalance_periods=body.rebalance_periods,
            category_counts=body.category_counts,
            uncategorized_count=body.uncategorized_count,
            selection_method=body.selection_method,
            min_abs_icir=body.min_abs_icir,
            min_abs_ic=body.min_abs_ic,
            corr_threshold=body.corr_threshold,
            weight_shrinkage=body.weight_shrinkage,
            benchmark=body.benchmark,
            submit_score=body.submit_score,
        )
    except MarkethonError as e:
        _handle_markethon_error(e)


# ---------------------------------------------------------------------------
# 选股
# ---------------------------------------------------------------------------


class SelectStocksRequest(BaseModel):
    names: list[str] = Field(..., description="参与打分的因子")
    weights: dict[str, float] | None = Field(default=None, description="因子权重")
    top_n: int = Field(default=20, ge=1, description="多头/空头各返回数量")
    date: str | None = Field(default=None, description="截面日期，null 为最新交易日")
    min_amount_cny: float = Field(default=0.0, ge=0.0, description="截面日最低成交额")
    min_listed_days: int = Field(default=0, ge=0, description="最低上市自然日数")


@router.post("/selection")
async def select_stocks(body: SelectStocksRequest) -> dict[str, Any]:
    """按截面 z-score 加权打分排序选股。"""
    client = get_markethon_client()
    try:
        return await client.select_stocks(
            names=body.names,
            weights=body.weights,
            top_n=body.top_n,
            date=body.date,
            min_amount_cny=body.min_amount_cny,
            min_listed_days=body.min_listed_days,
        )
    except MarkethonError as e:
        _handle_markethon_error(e)


# ---------------------------------------------------------------------------
# 项目现有因子 → Markethon qlib 映射辅助
# ---------------------------------------------------------------------------

_factor_store = FactorStore()
_map_store = MarkethonFactorMapStore()


# 内置公式因子到 qlib 表达式的建议映射（仅含可直接翻译的因子）。
_BUILTIN_FACTOR_TEMPLATES: dict[str, dict[str, Any]] = {
    "MA": {
        "template": "Mean($close, {n})",
        "example": "Mean($close, 20)",
        "supported": True,
        "note": "简单移动平均",
    },
    "SMA": {
        "template": "Mean($close, {n})",
        "example": "Mean($close, 20)",
        "supported": True,
        "note": "简单移动平均（别名）",
    },
    "STD": {
        "template": "Std($close, {n})",
        "example": "Std($close, 20)",
        "supported": True,
        "note": "滚动标准差",
    },
    "MOM": {
        "template": "$close - Ref($close, {n})",
        "example": "$close - Ref($close, 10)",
        "supported": True,
        "note": "动量",
    },
    "ROC": {
        "template": "($close - Ref($close, {n})) / Ref($close, {n})",
        "example": "($close - Ref($close, 5)) / Ref($close, 5)",
        "supported": True,
        "note": "变化率",
    },
    "BOLL": {
        "template": "($close - Mean($close, {n})) / (Std($close, {n}) * {std})",
        "example": "($close - Mean($close, 20)) / (Std($close, 20) * 2)",
        "supported": True,
        "note": "布林带偏离（需填 std 参数）",
    },
    "ZSCORE": {
        "template": "($close - Mean($close, {n})) / Std($close, {n})",
        "example": "($close - Mean($close, 20)) / Std($close, 20)",
        "supported": True,
        "note": "Z-Score 标准化",
    },
    "VOL_MA": {
        "template": "Mean($volume, {n})",
        "example": "Mean($volume, 5)",
        "supported": True,
        "note": "成交量均线",
    },
}


@router.get("/builtin_mappings")
async def get_builtin_mappings() -> dict[str, Any]:
    """
    返回当前项目内置因子到 Markethon qlib 表达式的建议映射。
    无法直接翻译的因子会返回 supported=false。
    """
    builtins = get_builtin_factors()
    result = {}
    for factor in builtins:
        name = factor["name"]
        if name in _BUILTIN_FACTOR_TEMPLATES:
            result[name] = {
                **factor,
                **_BUILTIN_FACTOR_TEMPLATES[name],
            }
        else:
            result[name] = {
                **factor,
                "supported": False,
                "template": None,
                "example": None,
                "note": "该因子无法自动映射为 Markethon qlib 表达式，请手动编写",
            }
    return {"mappings": result}


# ---------------------------------------------------------------------------
# 本地映射持久化
# ---------------------------------------------------------------------------


class FactorMapCreate(BaseModel):
    project_factor_id: str = Field(..., description="项目因子 ID（内置因子用 name，自定义因子用 id）")
    project_factor_name: str = Field(..., description="项目因子显示名")
    project_factor_mode: str = Field(default="formula", description="formula / python")
    qlib_expression: str = Field(..., description="对应的 Markethon qlib 表达式")
    markethon_name: str = Field(..., description="注册到 Markethon 的因子名")


class FactorMapUpdate(BaseModel):
    project_factor_id: str | None = Field(default=None)
    project_factor_name: str | None = Field(default=None)
    project_factor_mode: str | None = Field(default=None)
    qlib_expression: str | None = Field(default=None)
    markethon_name: str | None = Field(default=None)


@router.get("/factor_maps")
async def list_factor_maps() -> dict[str, Any]:
    """列出已保存的因子映射。"""
    return {"maps": [m.__dict__ for m in _map_store.list()]}


@router.post("/factor_maps")
async def create_or_update_factor_map(body: FactorMapCreate) -> dict[str, Any]:
    """创建或更新项目因子到 Markethon 的映射。"""
    mapping = _map_store.create_or_update(
        project_factor_id=body.project_factor_id,
        project_factor_name=body.project_factor_name,
        project_factor_mode=body.project_factor_mode,
        qlib_expression=body.qlib_expression,
        markethon_name=body.markethon_name,
    )
    return {"map": mapping.__dict__}


@router.put("/factor_maps/{map_id}")
async def update_factor_map(map_id: str, body: FactorMapUpdate) -> dict[str, Any]:
    """更新指定映射。"""
    update_data = body.model_dump(exclude_unset=True)
    mapping = _map_store.update(map_id, **update_data)
    if not mapping:
        raise HTTPException(status_code=404, detail="映射不存在")
    return {"map": mapping.__dict__}


@router.delete("/factor_maps/{map_id}")
async def delete_factor_map(map_id: str) -> dict[str, Any]:
    """删除指定映射。"""
    success = _map_store.delete(map_id)
    if not success:
        raise HTTPException(status_code=404, detail="映射不存在")
    return {"deleted": True}


# ---------------------------------------------------------------------------
# 批量注册映射因子
# ---------------------------------------------------------------------------


class DefineFactorItem(BaseModel):
    name: str = Field(..., description="因子名")
    expression: str = Field(..., description="qlib 表达式")


class BatchDefineRequest(BaseModel):
    factors: list[DefineFactorItem] = Field(..., description="待批量注册的因子列表")
    save_maps: bool = Field(default=True, description="是否同步保存到本地映射表")


@router.post("/factors/define_batch")
async def define_factors_batch(body: BatchDefineRequest) -> dict[str, Any]:
    """
    批量注册 qlib 表达式因子到 Markethon。
    返回每个因子的注册结果，失败的项会包含错误信息。
    """
    client = get_markethon_client()
    results = []
    successes = 0
    failures = 0

    for item in body.factors:
        try:
            data = await client.define_factor(name=item.name, expression=item.expression)
            results.append({"name": item.name, "ok": True, "data": data})
            successes += 1
        except MarkethonError as e:
            results.append({"name": item.name, "ok": False, "error": e.detail, "status": e.status_code})
            failures += 1

    return {"successes": successes, "failures": failures, "results": results}


# ---------------------------------------------------------------------------
# 天梯正式提交（/scores/submit）
# ---------------------------------------------------------------------------


@router.get("/data/current-symbols")
async def get_current_symbols() -> dict[str, Any]:
    """获取当前已加载的股票代码列表。"""
    client = get_markethon_client()
    try:
        return await client.get_current_symbols()
    except MarkethonError as e:
        _handle_markethon_error(e)


class SubmitLeaderboardRequest(BaseModel):
    names: list[str] = Field(..., description="候选因子池，>=10 个")
    submission_key: str = Field(..., description="幂等键，同一用户同一键只保存一条记录")
    train_months: int = Field(default=12)
    test_months: int = Field(default=3)
    step_months: int = Field(default=3)
    long_short: bool = Field(default=True)
    quantiles: int = Field(default=5)
    rebalance_periods: int = Field(default=5)
    benchmark: str = Field(default="IF")
    long_exposure: float = Field(default=0.95)
    short_exposure: float = Field(default=0.95)
    futures_cost: float = Field(default=0.0002)
    selection_method: str = Field(default="legacy")
    min_abs_icir: float = Field(default=0.10)
    min_abs_ic: float = Field(default=0.005)
    corr_threshold: float = Field(default=0.75)
    weight_shrinkage: float = Field(default=0.50)
    category_counts: dict[str, int] | None = Field(default=None)
    uncategorized_count: int | None = Field(default=None)
    submit_score: bool = Field(default=True)


@router.post("/scores/submit")
async def submit_leaderboard_score(body: SubmitLeaderboardRequest) -> dict[str, Any]:
    """天梯成绩正式提交。"""
    import logging
    logger = logging.getLogger(__name__)
    logger.warning(f"[/scores/submit] request names={body.names} key={body.submission_key}")
    client = get_markethon_client()
    try:
        return await client.submit_leaderboard_score(
            names=body.names,
            submission_key=body.submission_key,
            train_months=body.train_months,
            test_months=body.test_months,
            step_months=body.step_months,
            long_short=body.long_short,
            quantiles=body.quantiles,
            rebalance_periods=body.rebalance_periods,
            benchmark=body.benchmark,
            long_exposure=body.long_exposure,
            short_exposure=body.short_exposure,
            futures_cost=body.futures_cost,
            selection_method=body.selection_method,
            min_abs_icir=body.min_abs_icir,
            min_abs_ic=body.min_abs_ic,
            corr_threshold=body.corr_threshold,
            weight_shrinkage=body.weight_shrinkage,
            category_counts=body.category_counts,
            uncategorized_count=body.uncategorized_count,
            submit_score=body.submit_score,
        )
    except MarkethonError as e:
        _handle_markethon_error(e)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"天梯提交内部错误: {type(e).__name__}: {e}")
