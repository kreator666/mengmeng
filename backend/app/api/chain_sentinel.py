"""
算力链逃顶信号 API

- GET  /api/chain-sentinel/status     最新综合状态
- POST /api/chain-sentinel/scan       立即执行一次扫描（按交易日幂等覆盖）
- GET  /api/chain-sentinel/history    每日判级历史
- GET  /api/chain-sentinel/news       近期命中新闻
- GET  /api/chain-sentinel/dashboard  仪表盘录入查询（?quarter=2026Q3 可选）
- POST /api/chain-sentinel/dashboard  仪表盘录入/更新
- GET  /api/chain-sentinel/events     信号事件（灯色变化与推送记录）
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.chain_sentinel_service import run_scan
from app.core.notify import make_notifier
from app.data.sentinel_store import DASHBOARD_INDICATORS, SentinelStore

router = APIRouter(prefix="/api/chain-sentinel", tags=["chain-sentinel"])

_store = SentinelStore()


class DashboardEntry(BaseModel):
    quarter: str = Field(..., description="季度，如 2026Q3")
    indicator: str = Field(..., description=f"指标代码，可选: {DASHBOARD_INDICATORS}")
    status: str = Field(..., description="灯态: red/yellow/green")
    value_text: str = Field(default="", description="数值描述，如 7250亿E、1.23x")
    note: str = Field(default="", description="备注")


@router.get("/status")
async def get_status():
    """最新综合状态（灯色/评分/各层明细）"""
    latest = _store.latest_scan()
    if not latest:
        return {"ready": False, "message": "尚无扫描记录，请先 POST /api/chain-sentinel/scan"}
    return {
        "ready": True,
        **latest,
        "dashboard_status": _store.latest_dashboard_status(),
    }


@router.post("/scan")
async def trigger_scan():
    """立即执行一次完整扫描（拉取真实 Tiingo 数据，约需数十秒；灯色变化时按配置推送）"""
    try:
        result = await run_scan(store=_store, notifier=make_notifier())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"扫描失败: {e}")
    return result


@router.get("/history")
async def get_history(days: int = Query(default=90, ge=1, le=365)):
    """每日判级历史（灯色/评分曲线）"""
    return {"history": _store.scan_history(days)}


@router.get("/news")
async def get_news(days: int = Query(default=7, ge=1, le=30)):
    """近期命中负面关键词的链相关新闻"""
    return {"news": _store.recent_news(days)}


@router.get("/dashboard")
async def get_dashboard(quarter: str | None = Query(default=None)):
    """仪表盘录入查询；不传 quarter 返回全部"""
    return {
        "indicators": DASHBOARD_INDICATORS,
        "entries": _store.list_dashboard(quarter),
        "current_status": _store.latest_dashboard_status(),
    }


@router.post("/dashboard")
async def upsert_dashboard(entry: DashboardEntry):
    """录入/更新某季度某指标的灯态"""
    if entry.indicator not in DASHBOARD_INDICATORS:
        raise HTTPException(status_code=400, detail=f"未知指标: {entry.indicator}")
    if entry.status not in ("red", "yellow", "green"):
        raise HTTPException(status_code=400, detail=f"灯态必须是 red/yellow/green")
    _store.upsert_dashboard(
        entry.quarter, entry.indicator, entry.status, entry.value_text, entry.note
    )
    return {"ok": True, "current_status": _store.latest_dashboard_status()}


@router.get("/events")
async def get_events(limit: int = Query(default=50, ge=1, le=200)):
    """信号事件（灯色变化与推送记录）"""
    return {"events": _store.list_events(limit)}
