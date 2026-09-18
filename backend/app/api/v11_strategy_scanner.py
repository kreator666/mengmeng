# -*- coding: utf-8 -*-
"""
v11_core 策略扫描器 API

- POST /api/v11-scanner/scan    执行扫描（Gate.io 永续合约）
- GET  /api/v11-scanner/latest  最近一次扫描结果
- GET  /api/v11-scanner/history 历史扫描记录
"""
import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.core.v11_strategy_scanner import scan_gate_futures

router = APIRouter(prefix="/api/v11-scanner", tags=["v11-scanner"])

# 扫描结果存储目录（与底部趋势扫描器共用）
_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "scanner_results"
_DATA_DIR.mkdir(parents=True, exist_ok=True)

_PREFIX = "v11"


@router.post("/scan")
async def trigger_scan():
    """执行一次完整扫描（拉取 Gate.io 永续 K 线并计算 11 因子评分，耗时数十秒到数分钟）"""
    result = await scan_gate_futures()

    filename = f"{_PREFIX}_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(_DATA_DIR / filename, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    latest_path = _DATA_DIR / f"{_PREFIX}_latest.json"
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


@router.get("/latest")
async def get_latest():
    """获取最近一次扫描结果"""
    latest_path = _DATA_DIR / f"{_PREFIX}_latest.json"
    if not latest_path.exists():
        raise HTTPException(status_code=404, detail="尚无 v11 策略扫描记录，请先执行扫描")
    with open(latest_path, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/history")
async def get_history(limit: int = 20):
    """获取历史扫描记录列表"""
    files = sorted(_DATA_DIR.glob(f"{_PREFIX}_2*.json"), reverse=True)[:limit]
    records = []
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            records.append({
                "filename": fp.name,
                "scan_time": data.get("scan_time"),
                "total_pairs": data.get("total_pairs"),
                "scanned": data.get("scanned"),
                "top_score": data["ranking"][0]["score"] if data.get("ranking") else None,
            })
        except Exception:
            continue
    return {"records": records}
