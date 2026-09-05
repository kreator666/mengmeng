"""
按顺序提交 candidates.json 中的多个因子组合到天梯。
用法: python scripts/submit_candidates.py [backend/data/candidates.json]
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
TOKEN: str | None = None


def log(msg: str):
    print(msg, flush=True)


async def login(client: httpx.AsyncClient) -> str:
    global TOKEN
    resp = await client.post(
        f"{BASE_URL}/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    TOKEN = data.get("access_token") or data.get("token")
    log(f"已登录 {USERNAME}，token 前缀: {TOKEN[:12]}...")
    return TOKEN


async def api(client: httpx.AsyncClient, method: str, path: str, json=None, timeout=300):
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    resp = await client.request(method, f"{BASE_URL}{path}", json=json, headers=headers, timeout=timeout)
    if resp.status_code == 401:
        await login(client)
        headers["Authorization"] = f"Bearer {TOKEN}"
        resp = await client.request(method, f"{BASE_URL}{path}", json=json, headers=headers, timeout=timeout)
    if not resp.is_success:
        raise RuntimeError(f"{method} {path} [{resp.status_code}]: {resp.text[:800]}")
    return resp.json()


async def submit(client: httpx.AsyncClient, names: list[str], note: str) -> dict:
    if len(names) < 10:
        raise ValueError(f"因子数量不足 10 个: {len(names)}")

    submission_key = f"{USERNAME}-{note}-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    payload = {
        "names": names,
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
        "uncategorized_count": len(names),
        "submit_score": True,
    }

    log(f"\n===== 提交组合: {note} =====")
    log(f"submission_key: {submission_key}")
    log(f"因子数: {len(names)}")
    log(f"因子: {names}")

    result = await api(client, "POST", "/scores/submit", json=payload, timeout=7200)

    score = None
    std = result.get("standard_score")
    if isinstance(std, dict):
        score = std.get("score")
    elif isinstance(std, (int, float)):
        score = std
    log(f"standard_score: {score}")

    result_path = DATA_DIR / f"leaderboard_submit_{note}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log(f"结果已保存: {result_path}")

    return result


async def main():
    import sys
    path = sys.argv[1] if len(sys.argv) > 1 else str(DATA_DIR / "candidates.json")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    candidates = data.get("candidates", [])
    log(f"共 {len(candidates)} 个候选组合待提交")

    async with httpx.AsyncClient(timeout=httpx.Timeout(7200), follow_redirects=True) as client:
        await login(client)
        for i, c in enumerate(candidates, 1):
            note = c.get("note", f"candidate_{i:02d}")
            names = c.get("names", [])
            desc = c.get("desc", "")
            log(f"\n[{i}/{len(candidates)}] {note}: {desc}")
            try:
                await submit(client, names, note)
            except Exception as e:
                log(f"提交失败 [{note}]: {e}")
                # 记录失败以便后续排查
                fail_path = DATA_DIR / f"leaderboard_submit_{note}_failed.json"
                with open(fail_path, "w", encoding="utf-8") as f:
                    json.dump({"note": note, "names": names, "error": str(e)}, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    asyncio.run(main())
