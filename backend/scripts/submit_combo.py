"""
提交指定因子组合到天梯 /scores/submit。
从命令行读取 JSON 因子名列表，登录后提交并保存结果。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
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


async def submit(names: list[str], note: str = "", benchmark: str = "IF") -> dict:
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
        "benchmark": benchmark,
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

    log(f"\n提交组合: {note}")
    log(f"submission_key: {submission_key}")
    log(f"因子数: {len(names)}")
    log(f"因子: {names}")

    async with httpx.AsyncClient(timeout=httpx.Timeout(7200), follow_redirects=True) as client:
        await login(client)
        result = await api(client, "POST", "/scores/submit", json=payload, timeout=7200)

    score = result.get("standard_score", {}).get("score") if isinstance(result.get("standard_score"), dict) else result.get("standard_score")
    log(f"standard_score: {score}")
    log(f"metrics: {json.dumps(result.get('metrics', {}), ensure_ascii=False, indent=2)[:500]}")

    result_path = DATA_DIR / f"leaderboard_submit_{note}.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    log(f"结果已保存: {result_path}")

    return result


async def main():
    # 默认提交 BETA60->VSTD60 组合，支持命令行参数覆盖
    import argparse
    parser = argparse.ArgumentParser(description="提交因子组合到天梯")
    parser.add_argument("--factors", default=None, help="因子名 JSON 文件路径，或直接以逗号分隔的因子名")
    parser.add_argument("--note", default="v47_06_vstd60", help="提交结果文件名标识")
    parser.add_argument("--benchmark", default="IF", help="空头指数：IF/IC/IH/IM")
    args = parser.parse_args()

    # 47.06 基准上 BETA60 -> VSTD60（quantile 夏普/收益显著优于基准）
    default_names = [
        "GAP723", "PANIC_BUY",
        "QTLD60", "LOW0", "ROC60", "VSUMP60", "CNTN30", "QTLU30",
        "MIN20", "MIN30",
        "CORR10", "KLEN",
        "MIN5", "MIN10", "MIN60",
        "VSUMN60", "MA60", "CORD20", "STD10",
        "IMIN60", "VMA60", "RSV60", "SUMN30", "VSTD60",
    ]

    if args.factors:
        arg = args.factors
        if arg.endswith(".json"):
            with open(arg, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                names = data
            elif isinstance(data, dict):
                names = data.get("names", data.get("factors", []))
            else:
                raise ValueError("JSON 文件需为列表或包含 names 的字典")
        else:
            names = [s.strip() for s in arg.split(",") if s.strip()]
    else:
        names = default_names

    await submit(names, args.note, args.benchmark)


if __name__ == "__main__":
    asyncio.run(main())
