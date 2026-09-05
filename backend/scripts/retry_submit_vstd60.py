"""
自动重试提交 BETA60->VSTD60 组合到 Markethon 天梯。
当计算集群 inflight 低于阈值时提交，繁忙时等待后重试。
"""
from __future__ import annotations

import asyncio
import json
import os
import time
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
    log(f"已登录，token 前缀: {TOKEN[:12]}...")
    return TOKEN


async def api(client: httpx.AsyncClient, method: str, path: str, json=None, timeout=60):
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


async def get_inflight_total(client: httpx.AsyncClient) -> int:
    data = await api(client, "GET", "/status")
    cp = data.get("compute_pool", {})
    workers = cp.get("workers", [])
    return sum(w.get("inflight", 0) for w in workers)


async def submit(client: httpx.AsyncClient) -> dict:
    submission_key = f"{USERNAME}-v47_06_vstd60-auto-{datetime.now().strftime('%Y%m%d%H%M%S')}"
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
    log(f"提交 VSTD60 组合，key={submission_key}")
    result = await api(client, "POST", "/scores/submit", json=payload, timeout=7200)
    score = result.get("standard_score", {}).get("score") if isinstance(result.get("standard_score"), dict) else result.get("standard_score")
    log(f"standard_score: {score}")
    result_path = DATA_DIR / f"leaderboard_submit_v47_06_vstd60_auto.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    log(f"结果已保存: {result_path}")
    return result


async def main():
    max_retries = 50
    check_interval = 600  # 10 分钟检查一次
    inflight_threshold = 5  # 低于此值才尝试提交

    async with httpx.AsyncClient(timeout=7200) as client:
        await login(client)

        for attempt in range(1, max_retries + 1):
            try:
                inflight = await get_inflight_total(client)
                log(f"第 {attempt} 次检查，计算集群 inflight={inflight}")

                if inflight <= inflight_threshold:
                    log("集群空闲，尝试提交...")
                    try:
                        result = await submit(client)
                        score = result.get("standard_score", {}).get("score") if isinstance(result.get("standard_score"), dict) else result.get("standard_score")
                        if score:
                            log(f"提交成功，standard_score={score}")
                            return
                        else:
                            log("提交返回但 score 为 0，可能是覆盖率问题，停止重试")
                            return
                    except RuntimeError as e:
                        log(f"提交失败: {e}")
                else:
                    log(f"集群繁忙，{check_interval} 秒后重试...")

            except Exception as e:
                log(f"检查失败: {e}")

            await asyncio.sleep(check_interval)

        log("达到最大重试次数，停止")


if __name__ == "__main__":
    asyncio.run(main())
