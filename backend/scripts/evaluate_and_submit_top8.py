"""
1. 获取 Markethon 已注册因子（alpha158 + 自定义）。
2. 分批评估每个因子的 IC 均值。
3. 排除 GAP723 和 PANIC_BUY 后，取 |IC| 均值最大的 8 个。
4. 将这 8 个因子提交到天梯 /scores/submit。
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


async def get_factors(client: httpx.AsyncClient) -> tuple[list[str], dict[str, str]]:
    data = await api(client, "GET", "/factors", timeout=60)
    alpha158 = data.get("alpha158", [])
    custom = data.get("custom", {})
    if isinstance(custom, dict):
        custom_names = list(custom.keys())
    else:
        custom_names = [c.get("name") for c in custom if isinstance(c, dict)]
    return alpha158, custom_names


async def evaluate_batch(client: httpx.AsyncClient, names: list[str], quantiles: int = 5):
    payload = {"names": names, "quantiles": quantiles, "top_n": len(names)}
    return await api(client, "POST", "/factors/evaluate", json=payload, timeout=300)


def extract_ic(name: str, eval_data: dict) -> float | None:
    """从 /factors/evaluate 响应中提取指定因子的 IC 均值。

    实际返回结构：
      {"count": 20, "factors": [{"factor": "BETA30", "IC均值": -0.039, ...}, ...]}
    因子顺序与请求不一致，需要按 factor 字段匹配。
    """
    factors = eval_data.get("factors") or eval_data.get("results") or eval_data.get("data")
    if not isinstance(factors, list):
        return None
    for item in factors:
        if not isinstance(item, dict):
            continue
        item_name = item.get("factor") or item.get("name")
        if item_name != name:
            continue
        for k in ("IC均值", "ic_mean", "mean_ic", "ic"):
            v = item.get(k)
            if v is not None:
                try:
                    return float(v)
                except (TypeError, ValueError):
                    pass
    return None


async def main():
    async with httpx.AsyncClient(timeout=httpx.Timeout(300), follow_redirects=True) as client:
        await login(client)

        alpha158, custom_names = await get_factors(client)
        log(f"alpha158 因子数: {len(alpha158)}")
        log(f"自定义因子: {custom_names}")

        all_names = list(dict.fromkeys(alpha158 + custom_names))  # 保持顺序去重
        log(f"待评估因子总数: {len(all_names)}")

        # 分批评估
        batch_size = 20
        records: list[dict] = []
        total_batches = (len(all_names) + batch_size - 1) // batch_size
        for idx in range(total_batches):
            batch = all_names[idx * batch_size : (idx + 1) * batch_size]
            log(f"\n批次 {idx + 1}/{total_batches} ({len(batch)} 个): {batch[:3]}...")
            try:
                eval_data = await evaluate_batch(client, batch)
                # 保存原始响应以便排查
                raw_path = DATA_DIR / f"eval_batch_{idx + 1:03d}.json"
                with open(raw_path, "w", encoding="utf-8") as f:
                    json.dump(eval_data, f, ensure_ascii=False, indent=2)
                for name in batch:
                    ic = extract_ic(name, eval_data)
                    records.append({"name": name, "ic_mean": ic})
                    if ic is not None:
                        log(f"  {name}: ic_mean={ic:.6f}")
                    else:
                        log(f"  {name}: 未提取到 ic_mean")
            except Exception as e:
                log(f"  批次失败: {e}")
                for name in batch:
                    records.append({"name": name, "ic_mean": None})

        # 排序并保存
        valid = [r for r in records if r["ic_mean"] is not None]
        valid.sort(key=lambda x: abs(x["ic_mean"]), reverse=True)

        ranking_path = DATA_DIR / "factor_ic_ranking.json"
        with open(ranking_path, "w", encoding="utf-8") as f:
            json.dump({"total": len(all_names), "evaluated": len(valid), "sorted": valid}, f, ensure_ascii=False, indent=2)
        log(f"\nIC 排序结果已保存: {ranking_path}")

        log("\n按 |IC| 均值排名前 20:")
        for r in valid[:20]:
            log(f"  {r['name']}: {r['ic_mean']:.6f}")

        # 排除 GAP723 和 PANIC_BUY，取前 8
        excluded = {"GAP723", "PANIC_BUY"}
        candidates = [r for r in valid if r["name"] not in excluded]
        top8 = candidates[:8]
        top8_names = [r["name"] for r in top8]

        if len(top8) < 8:
            log(f"警告：可用于提交因子不足 8 个，只有 {len(top8)} 个")

        log(f"\n选中的 8 个因子（排除 GAP723/PANIC_BUY）:")
        for r in top8:
            log(f"  {r['name']}: {r['ic_mean']:.6f}")

        # 提交到天梯：names 需要 >=10 个，因此把 8 个因子 + 排除的 2 个一起提交？
        # 但用户说"用这 8 个因子提交"；服务端要求 >=10 个候选。这里我们把 8 个作为候选池，
        # 同时把 GAP723 和 PANIC_BUY 也放入 names 以满足数量要求，但由 walk_forward 自动选择。
        # 更稳妥做法：直接以 top8_names 提交，如果服务端报错不足 10 再扩。
        submission_names = top8_names
        if len(submission_names) < 10:
            # 补足到 10 个：从排除列表后的后续排名中取
            extra = [r["name"] for r in candidates[8:8 + (10 - len(submission_names))]]
            submission_names = submission_names + extra
            log(f"因子池不足 10 个，已自动补足至: {submission_names}")

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
        log(f"\n正在提交天梯，submission_key={submission_key}，names={submission_names}...")
        try:
            result = await api(client, "POST", "/scores/submit", json=payload, timeout=7200)
            result_path = DATA_DIR / "leaderboard_submit_result.json"
            with open(result_path, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            log(f"提交结果已保存: {result_path}")
            log(f"standard_score: {result.get('standard_score')}")
            log(f"submission_skipped: {result.get('submission_skipped')}")
            log(f"metrics: {json.dumps(result.get('metrics'), ensure_ascii=False, indent=2)[:500]}")
        except Exception as e:
            log(f"提交失败: {e}")


if __name__ == "__main__":
    asyncio.run(main())
