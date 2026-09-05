"""
在 47.06 基准组合上做有针对性的单因子替换，用 walk_forward（submit_score=False）离线比较。
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
    "QTLD60", "LOW0", "ROC60", "VSUMP60", "CNTN30", "QTLU30",
    "MIN20", "MIN30",
    "CORR10", "KLEN",
    "MIN5", "MIN10", "MIN60",
    "VSUMN60", "MA60", "CORD20", "STD10",
    "IMIN60", "VMA60", "RSV60", "SUMN30", "BETA60",
]

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
    log(f"\n[{name}] walk_forward 开始...")
    result = await api(client, "POST", "/backtest/walk_forward", json=payload, timeout=7200)
    ss = result.get("standard_score", {})
    score = ss.get("score") if isinstance(ss, dict) else result.get("standard_score")
    log(f"[{name}] standard_score: {score}")
    out_path = DATA_DIR / f"walkforward_{name}.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"[{name}] 结果已保存: {out_path}")
    return result


def replace(names: list[str], old: str, new: str) -> list[str]:
    return [new if n == old else n for n in names]


async def main():
    variants = [
        ("repl_beta60_klow", replace(BASELINE, "BETA60", "KLOW")),
        ("repl_beta60_kup", replace(BASELINE, "BETA60", "KUP")),
        ("repl_beta60_cord30", replace(BASELINE, "BETA60", "CORD30")),
        ("repl_beta60_std5", replace(BASELINE, "BETA60", "STD5")),
        ("repl_imin60_kup", replace(BASELINE, "IMIN60", "KUP")),
        ("repl_imin60_klow", replace(BASELINE, "IMIN60", "KLOW")),
        ("repl_std10_std5", replace(BASELINE, "STD10", "STD5")),
        ("repl_sumn30_sump30", replace(BASELINE, "SUMN30", "SUMP30")),
        ("repl_ma60_ma30", replace(BASELINE, "MA60", "MA30")),
        ("repl_min10_min60", replace(BASELINE, "MIN10", "MIN60")),
    ]

    async with httpx.AsyncClient(timeout=7200) as client:
        await login(client)
        for name, names in variants:
            try:
                await walk_forward(client, name, names)
            except Exception as e:
                log(f"[{name}] 失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
