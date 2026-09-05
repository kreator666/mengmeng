"""
重新登录 -> 检查/加载 IM 官方池 -> 检查/注册 GAP723/PANIC_BUY -> 提交 VSTD60 组合。
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from pathlib import Path

import httpx

BASE_URL = os.environ.get("MARKETHON_BASE_URL", "https://markethon.fit:19371").rstrip("/")
USERNAME = os.environ.get("MARKETHON_USERNAME", "darkspell")
PASSWORD = os.environ.get("MARKETHON_PASSWORD", "darkwave30133")
DATA_DIR = Path("d:/agent/mengmeng/backend/data")
DATA_DIR.mkdir(exist_ok=True)

NAMES = [
    "GAP723", "PANIC_BUY",
    "QTLD60", "LOW0", "ROC60", "VSUMP60", "CNTN30", "QTLU30",
    "MIN20", "MIN30",
    "CORR10", "KLEN",
    "MIN5", "MIN10", "MIN60",
    "VSUMN60", "MA60", "CORD20", "STD10",
    "IMIN60", "VMA60", "RSV60", "SUMN30", "VSTD60",
]

CUSTOM_FACTORS = {
    "GAP723": "($open - Ref($close, 1)) / Ref($close, 1)",
    "PANIC_BUY": "($low - ($open + $close - Abs($open - $close)) / 2) / ($high - $low) * ($volume / Mean($volume, 5))",
}

TOKEN: str | None = None


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


async def login(client: httpx.AsyncClient) -> str:
    global TOKEN
    r = await client.post(
        f"{BASE_URL}/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    TOKEN = data.get("access_token") or data.get("token")
    log(f"已登录 {USERNAME}，token 前缀: {TOKEN[:12]}...")
    return TOKEN


async def api(client: httpx.AsyncClient, method: str, path: str, json=None, timeout=60):
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    r = await client.request(method, f"{BASE_URL}{path}", json=json, headers=headers, timeout=timeout)
    if r.status_code == 401:
        log("token 失效，重新登录")
        await login(client)
        headers["Authorization"] = f"Bearer {TOKEN}"
        r = await client.request(method, f"{BASE_URL}{path}", json=json, headers=headers, timeout=timeout)
    if not r.is_success:
        raise RuntimeError(f"{method} {path} [{r.status_code}]: {r.text[:500]}")
    return r.json()


async def ensure_data(client: httpx.AsyncClient):
    status = await api(client, "GET", "/status", timeout=60)
    log(f"当前状态: {json.dumps(status, ensure_ascii=False, indent=2)[:600]}")

    manifest = status.get("data_manifest", {}) or {}
    universe = manifest.get("universe")
    start = manifest.get("start")
    end = manifest.get("end")
    symbol_count = manifest.get("symbol_count")

    need_reload = False
    if universe != "IM":
        log(f"universe 不是 IM，需要重新加载")
        need_reload = True
    if start != "2020-08-21":
        log(f"start 不是 2020-08-21，需要重新加载")
        need_reload = True
    if end != "2026-08-20":
        log(f"end 不是 2026-08-20，需要重新加载")
        need_reload = True
    if (symbol_count or 0) < 500:
        log(f"symbol_count={symbol_count}，需要重新加载")
        need_reload = True

    if not need_reload:
        log("数据已预热，跳过加载")
        return

    log("开始加载 IM 官方池数据 2020-08-21 ~ 2026-08-20 ...")
    payload = {
        "limit": 0,
        "universe": "IM",
        "start": "2020-08-21",
        "end": "2026-08-20",
        "alpha360": False,
    }
    result = await api(client, "POST", "/data/load", json=payload, timeout=7200)
    log(f"数据加载结果: {json.dumps(result, ensure_ascii=False, indent=2)[:400]}")


async def ensure_factors(client: httpx.AsyncClient):
    data = await api(client, "GET", "/factors", timeout=60)
    existing = {f.get("name", f): True for f in data.get("factors", [])}
    log(f"已注册因子数: {len(existing)}")

    for name, expr in CUSTOM_FACTORS.items():
        if name in existing:
            log(f"因子 {name} 已注册，跳过")
            continue
        log(f"注册因子 {name}: {expr}")
        await api(client, "POST", "/factors/define", json={"name": name, "expression": expr}, timeout=300)
        log(f"因子 {name} 注册完成")


async def submit(client: httpx.AsyncClient) -> dict:
    submission_key = f"{USERNAME}-v47_06_vstd60-reload-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    payload = {
        "names": NAMES,
        "submission_key": submission_key,
        "train_months": 12,
        "test_months": 3,
        "step_months": 3,
        "long_short": True,
        "quantiles": 5,
        "rebalance_periods": 5,
        "benchmark": "IF",
        "long_exposure": 0.95,
        "short_exposure": 0.95,
        "futures_cost": 0.0002,
        "selection_method": "legacy",
        "min_abs_icir": 0.10,
        "min_abs_ic": 0.005,
        "corr_threshold": 0.75,
        "weight_shrinkage": 0.50,
        "category_counts": None,
        "uncategorized_count": len(NAMES),
        "submit_score": True,
    }
    log(f"\n提交 VSTD60 组合，key={submission_key}")
    result = await api(client, "POST", "/scores/submit", json=payload, timeout=7200)

    score = result.get("standard_score", {}).get("score") if isinstance(result.get("standard_score"), dict) else result.get("standard_score")
    log(f"standard_score: {score}")
    log(f"eligible: {result.get('eligible')}, reason: {result.get('score_reason')}")

    result_path = DATA_DIR / f"leaderboard_submit_v47_06_vstd60_reload.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"结果已保存: {result_path}")
    return result


async def main():
    async with httpx.AsyncClient(timeout=7200) as client:
        await login(client)
        await ensure_data(client)
        await ensure_factors(client)
        await submit(client)


if __name__ == "__main__":
    asyncio.run(main())
