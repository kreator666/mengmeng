"""
把 47.06 基准组合精简到 ~12 个不重复因子，用 walk_forward（submit_score=False）离线比较。
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx

BASE_URL = os.environ.get("MARKETHON_BASE_URL", "https://markethon.fit:19371").rstrip("/")
USERNAME = os.environ.get("MARKETHON_USERNAME", "darkspell")
PASSWORD = os.environ.get("MARKETHON_PASSWORD", "darkwave30133")
DATA_DIR = Path("d:/agent/mengmeng/backend/data")
DATA_DIR.mkdir(exist_ok=True)

BASELINE = [
    "GAP723", "PANIC_BUY",
    "ROC60", "MA60", "MIN10", "CORR10", "VMA60", "VSUMN60", "VSUMP60",
    "LOW0", "STD10", "BETA60",
]

VARIANTS = {
    "v12_core": BASELINE,
    "v12_klen": [
        "GAP723", "PANIC_BUY",
        "ROC60", "MA60", "KLEN", "CORR10", "VMA60", "VSUMN60", "VSUMP60",
        "LOW0", "STD10", "BETA60",
    ],
    "v12_qtld": [
        "GAP723", "PANIC_BUY",
        "ROC60", "MA60", "MIN10", "CORR10", "VMA60", "VSUMN60", "VSUMP60",
        "LOW0", "STD10", "QTLD60",
    ],
    "v12_sumn": [
        "GAP723", "PANIC_BUY",
        "ROC60", "MA60", "MIN10", "CORR10", "VMA60", "VSUMN60", "VSUMP60",
        "LOW0", "STD10", "SUMN30",
    ],
    "v11_core": [
        "GAP723", "PANIC_BUY",
        "ROC60", "MA60", "CORR10", "VMA60", "VSUMN60", "VSUMP60",
        "LOW0", "STD10", "BETA60",
    ],
}

TOKEN: str | None = None


def log(msg: str):
    print(msg, flush=True)


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
    log(f"已登录，token 前缀: {TOKEN[:12]}...")
    return TOKEN


async def api(client: httpx.AsyncClient, method: str, path: str, json=None, timeout=300):
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    r = await client.request(method, f"{BASE_URL}{path}", json=json, headers=headers, timeout=timeout)
    if r.status_code == 401:
        await login(client)
        headers["Authorization"] = f"Bearer {TOKEN}"
        r = await client.request(method, f"{BASE_URL}{path}", json=json, headers=headers, timeout=timeout)
    if not r.is_success:
        raise RuntimeError(f"{method} {path} [{r.status_code}]: {r.text[:500]}")
    return r.json()


async def walk_forward(client: httpx.AsyncClient, name: str, names: list[str]) -> dict:
    payload = {
        "names": names,
        "train_months": 12,
        "test_months": 3,
        "step_months": 3,
        "long_short": True,
        "quantiles": 5,
        "rebalance_periods": 5,
        "benchmark": "IF",
        "selection_method": "legacy",
        "min_abs_icir": 0.10,
        "min_abs_ic": 0.005,
        "corr_threshold": 0.75,
        "weight_shrinkage": 0.50,
        "category_counts": None,
        "uncategorized_count": len(names),
        "submit_score": False,
    }
    log(f"\n[{name}] 因子数={len(names)} walk_forward 开始...")
    result = await api(client, "POST", "/backtest/walk_forward", json=payload, timeout=7200)
    ss = result.get("standard_score", {})
    score = ss.get("score") if isinstance(ss, dict) else result.get("standard_score")
    log(f"[{name}] standard_score: {score}")
    out_path = DATA_DIR / f"walkforward_{name}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"[{name}] 结果已保存: {out_path}")
    return result


async def main():
    async with httpx.AsyncClient(timeout=7200) as client:
        await login(client)
        for name, names in VARIANTS.items():
            try:
                await walk_forward(client, name, names)
            except Exception as e:
                log(f"[{name}] 失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
