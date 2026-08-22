"""列出 Markethon 已注册因子，分批评估 IC，并输出排序结果。"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import httpx

BASE_URL = os.environ.get("MARKETHON_BASE_URL", "https://markethon.fit:19371").rstrip("/")
USERNAME = os.environ.get("MARKETHON_USERNAME", "darkspell")
PASSWORD = os.environ.get("MARKETHON_PASSWORD", "darkwave30133")

TOKEN: str | None = None


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
    print(f"已登录，token 前缀: {TOKEN[:12]}...")
    return TOKEN


async def request(client: httpx.AsyncClient, method: str, path: str, json=None, timeout=180):
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    resp = await client.request(method, f"{BASE_URL}{path}", json=json, headers=headers, timeout=timeout)
    if resp.status_code == 401:
        await login(client)
        headers["Authorization"] = f"Bearer {TOKEN}"
        resp = await client.request(method, f"{BASE_URL}{path}", json=json, headers=headers, timeout=timeout)
    if not resp.is_success:
        raise RuntimeError(f"{method} {path} [{resp.status_code}]: {resp.text[:500]}")
    return resp.json()


async def list_factors(client: httpx.AsyncClient):
    data = await request(client, "GET", "/factors")
    return data


async def evaluate_batch(client: httpx.AsyncClient, names: list[str], quantiles: int = 5):
    payload = {"names": names, "quantiles": quantiles, "top_n": len(names)}
    data = await request(client, "POST", "/factors/evaluate", json=payload, timeout=300)
    return data


def extract_ic_mean(factor_name: str, eval_data: dict) -> float | None:
    """从 evaluate 结果中提取指定因子的 IC 均值。"""
    results = eval_data.get("results", eval_data.get("factors", eval_data))
    if isinstance(results, dict):
        results = [results]
    if not isinstance(results, list):
        return None
    for item in results:
        if isinstance(item, dict) and (item.get("name") or item.get("factor")) == factor_name:
            ic_mean = item.get("ic_mean") or item.get("mean_ic") or item.get("ic")
            if ic_mean is not None:
                return float(ic_mean)
    return None


async def main():
    async with httpx.AsyncClient(timeout=httpx.Timeout(300), follow_redirects=True) as client:
        await login(client)

        # 1. 列出所有因子
        factors_data = await list_factors(client)
        all_names = []
        if isinstance(factors_data, dict):
            all_names = factors_data.get("factors", factors_data.get("names", factors_data.get("data", [])))
        if isinstance(all_names, list) and all_names and isinstance(all_names[0], dict):
            all_names = [f.get("name") or f.get("factor") for f in all_names]
        all_names = [n for n in all_names if n]
        print(f"Markethon 已注册因子总数: {len(all_names)}")
        print("前 30 个:", all_names[:30])

        # 2. 分批评估（每批 20 个），保存结果
        batch_size = 20
        records = []
        for i in range(0, len(all_names), batch_size):
            batch = all_names[i : i + batch_size]
            print(f"\n评估批次 {i // batch_size + 1}/{(len(all_names) + batch_size - 1) // batch_size}: {batch[:5]}... 共 {len(batch)} 个")
            try:
                eval_data = await evaluate_batch(client, batch)
                # 保存原始结果
                raw_path = Path(f"d:/agent/mengmeng/backend/data/eval_batch_{i // batch_size + 1:03d}.json")
                with open(raw_path, "w", encoding="utf-8") as f:
                    json.dump(eval_data, f, ensure_ascii=False, indent=2)
                # 提取每个因子的 IC 均值
                for name in batch:
                    ic = extract_ic_mean(name, eval_data)
                    records.append({"name": name, "ic_mean": ic})
                    print(f"  {name}: ic_mean={ic}")
            except Exception as e:
                print(f"  批次失败: {e}")
                for name in batch:
                    records.append({"name": name, "ic_mean": None})

        # 3. 排序并保存
        valid_records = [r for r in records if r["ic_mean"] is not None]
        valid_records.sort(key=lambda x: abs(x["ic_mean"]), reverse=True)

        output = {
            "total": len(all_names),
            "evaluated": len(valid_records),
            "sorted_by_abs_ic": valid_records,
        }
        out_path = Path("d:/agent/mengmeng/backend/data/factor_ic_ranking.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"\n排序结果已保存: {out_path}")
        print("\n按 |IC| 均值排序前 15:")
        for r in valid_records[:15]:
            print(f"  {r['name']}: {r['ic_mean']:.6f}")


if __name__ == "__main__":
    asyncio.run(main())
