"""
快速对比基准组合 vs. 强因子候选池的 /backtest/quantile 指标。
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

BASELINE = [
    "GAP723", "PANIC_BUY",
    "QTLD60", "LOW0", "ROC60", "VSUMP60", "CNTN30", "QTLU30",
    "MIN20", "MIN30",
    "CORR10", "KLEN",
    "MIN5", "MIN10", "MIN60",
    "VSUMN60", "MA60", "CORD20", "STD10",
    "IMIN60", "VMA60", "RSV60", "SUMN30", "BETA60",
]

STRONG24 = [
    "GAP723", "PANIC_BUY",
    "KLEN", "KLOW", "LOW0",
    "MIN10", "MIN60",
    "QTLD30", "QTLD60",
    "ROC30", "ROC60",
    "STD5", "STD10",
    "CORR10", "CORD20",
    "VSUMN60", "VSUMP60", "VMA60",
    "SUMN30", "SUMP30",
    "MA30", "MA60",
    "IMIN60", "RSV60",
]

STRONG24_V2 = [
    "GAP723", "PANIC_BUY",
    "KLEN", "KLOW", "LOW0",
    "MIN10", "MIN30", "MIN60",
    "QTLD20", "QTLD60",
    "ROC20", "ROC60",
    "STD10", "STD20",
    "CORR10", "CORD20", "CORD30",
    "VSUMN60", "VSUMP60", "VMA60",
    "SUMN30", "SUMD30",
    "MA30", "MA60",
]

COMBOS = {
    "baseline": BASELINE,
    "strong24": STRONG24,
    "strong24_v2": STRONG24_V2,
}


def extract_metrics(data: dict) -> dict:
    m = data.get("metrics", {})
    keys = list(m.keys())
    def get(idx, default=None):
        return m.get(keys[idx], default) if 0 <= idx < len(keys) else default
    return {
        "total_return": get(0),
        "annual_return": get(1),
        "annual_volatility": get(2),
        "sharpe": get(3),
        "max_drawdown": get(4),
        "max_drawdown_days": get(5),
        "win_rate": get(6),
        "trading_days": get(7),
        "initial_value": get(8),
        "alpha": get(9),
        "beta": get(10),
        "IF_return": get(11),
    }


async def login(client: httpx.AsyncClient) -> str:
    r = await client.post(
        f"{BASE_URL}/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        timeout=60,
    )
    r.raise_for_status()
    data = r.json()
    return data.get("access_token") or data.get("token")


async def quantile(client: httpx.AsyncClient, token: str, names: list[str]) -> dict:
    payload = {
        "names": names,
        "long_short": True,
        "periods": 5,
        "quantiles": 5,
        "benchmark": "IF",
    }
    r = await client.post(
        f"{BASE_URL}/backtest/quantile",
        json=payload,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json", "Accept": "application/json"},
        timeout=300,
    )
    r.raise_for_status()
    for enc in ("utf-8", "gbk", "gb2312"):
        try:
            text = r.content.decode(enc)
            return json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    return r.json()


async def main():
    async with httpx.AsyncClient(timeout=300) as client:
        token = await login(client)
        results = []
        for name, factors in COMBOS.items():
            print(f"\n[{name}] 因子数={len(factors)}")
            try:
                data = await quantile(client, token, factors)
                metrics = extract_metrics(data)
                print(json.dumps(metrics, ensure_ascii=False, indent=2))
                results.append({"name": name, "factors": factors, "metrics": metrics})
            except Exception as e:
                print(f"失败: {e}")
                results.append({"name": name, "factors": factors, "error": str(e)})

        out_path = DATA_DIR / "quantile_test_results.json"
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
