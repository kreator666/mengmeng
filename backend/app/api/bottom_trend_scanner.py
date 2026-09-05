# -*- coding: utf-8 -*-
"""
底部趋势扫描器 API

- POST /api/bottom-trend-scanner/scan   执行扫描（支持 gate/binance/okx）
- GET  /api/bottom-trend-scanner/history 历史扫描记录
"""
import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.bottom_trend_scanner import SCANNERS

router = APIRouter(prefix="/api/bottom-trend-scanner", tags=["bottom-trend-scanner"])

# 扫描结果存储目录
_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "scanner_results"
_DATA_DIR.mkdir(parents=True, exist_ok=True)


class ScanRequest(BaseModel):
    exchange: str = Field(default="gate", description="交易所: gate / binance / okx")


@router.post("/scan")
async def trigger_scan(req: ScanRequest):
    """执行一次完整扫描（拉取 K 线数据，耗时数十秒到数分钟）"""
    exchange = req.exchange.lower()
    scanner = SCANNERS.get(exchange)
    if not scanner:
        raise HTTPException(status_code=400, detail=f"不支持的交易所: {exchange}，可选: gate / binance / okx")

    result = await scanner()

    # 保存扫描结果
    filename = f"{exchange}_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    filepath = _DATA_DIR / filename
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    # 同时保存为 latest
    latest_path = _DATA_DIR / f"{exchange}_latest.json"
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


@router.get("/latest")
async def get_latest(exchange: str = Query(default="gate", description="交易所: gate / binance / okx")):
    """获取最近一次扫描结果"""
    exchange = exchange.lower()
    latest_path = _DATA_DIR / f"{exchange}_latest.json"
    if not latest_path.exists():
        raise HTTPException(status_code=404, detail=f"尚无 {exchange} 的扫描记录，请先执行扫描")
    with open(latest_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/history")
async def get_history(exchange: str = Query(default="gate", description="交易所: gate / binance / okx"), limit: int = Query(default=20, ge=1, le=100)):
    """获取历史扫描记录列表"""
    exchange = exchange.lower()
    files = sorted(_DATA_DIR.glob(f"{exchange}_2*.json"), reverse=True)[:limit]
    records = []
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            records.append({
                "filename": fp.name,
                "scan_time": data.get("scan_time"),
                "exchange": data.get("exchange"),
                "total_pairs": data.get("total_pairs"),
                "trend_count": len(data.get("trend_candidates", [])),
                "bottom_count": len(data.get("bottom_candidates", [])),
            })
        except Exception:
            continue
    return {"records": records}
