"""解析已保存的 eval_batch_*.json，取 IC 均值前 8（排除 GAP723/PANIC_BUY），提交天梯。"""
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
TOKEN: str | None = None


def log(msg: str):
    print(msg)


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
    log(f"已登录 darkspell，token 前缀: {TOKEN[:12]}...")
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


def parse_batches() -> list[dict]:
    records = []
    for path in sorted(DATA_DIR.glob("eval_batch_*.json")):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        factors = data.get("factors", [])
        for item in factors:
            if not isinstance(item, dict):
                continue
            name = item.get("factor") or item.get("name")
            ic = item.get("IC均值") or item.get("ic_mean") or item.get("ic")
            if name and ic is not None:
                try:
                    records.append({"name": name, "ic_mean": float(ic)})
                except (TypeError, ValueError):
                    pass
    return records


async def main():
    records = parse_batches()
    # 去重，保留第一次出现
    seen = set()
    unique = []
    for r in records:
        if r["name"] not in seen:
            seen.add(r["name"])
            unique.append(r)

    unique.sort(key=lambda x: abs(x["ic_mean"]), reverse=True)

    ranking_path = DATA_DIR / "factor_ic_ranking_fixed.json"
    with open(ranking_path, "w", encoding="utf-8") as f:
        json.dump({"evaluated": len(unique), "sorted": unique}, f, ensure_ascii=False, indent=2)
    log(f"IC 排序结果已保存: {ranking_path}")

    log(f"\n共评估 {len(unique)} 个因子，按 |IC| 均值排名前 20:")
    for r in unique[:20]:
        log(f"  {r['name']}: {r['ic_mean']:.6f}")

    excluded = {"GAP723", "PANIC_BUY"}
    candidates = [r for r in unique if r["name"] not in excluded]
    top8 = candidates[:8]
    top8_names = [r["name"] for r in top8]

    log(f"\n排除 GAP723/PANIC_BUY 后，|IC| 均值最大的 8 个因子:")
    for r in top8:
        log(f"  {r['name']}: {r['ic_mean']:.6f}")

    # 天梯正式提交要求至少 10 个有效因子；用排除后的前 10 个作为候选池提交
    top10 = candidates[:10]
    submission_names = [r["name"] for r in top10]
    log(f"\n因提交要求 >=10 个因子，实际提交候选池（排除 GAP723/PANIC_BUY 前 10）:")
    for r in top10:
        log(f"  {r['name']}: {r['ic_mean']:.6f}")
    submission_key = f"darkspell-top8-{datetime.now().strftime('%Y%m%d%H%M%S')}"
    payload = {
        "names": submission_names,
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
        "uncategorized_count": len(submission_names),
        "submit_score": True,
    }

    async with httpx.AsyncClient(timeout=httpx.Timeout(7200), follow_redirects=True) as client:
        await login(client)
        log(f"\n正在提交天梯，submission_key={submission_key}，names={submission_names}...")
        try:
            result = await api(client, "POST", "/scores/submit", json=payload, timeout=7200)
            result_path = DATA_DIR / "leaderboard_submit_top8_result.json"
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            log(f"提交结果已保存: {result_path}")
            log(f"standard_score: {result.get('standard_score')}")
            log(f"submission_skipped: {result.get('submission_skipped')}")
            metrics = result.get("metrics", {})
            log(f"metrics 摘要: {json.dumps(metrics, ensure_ascii=False, indent=2)[:1000]}")
        except Exception as e:
            log(f"提交失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
