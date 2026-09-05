"""
使用 Markethon /backtest/quantile 快速筛选候选组合。
/scores/submit 故障期间，用 quantile 回测做相对排序。
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx

BASE_URL = "https://markethon.fit:19371"
USERNAME = "darkspell"
PASSWORD = "darkwave30133"
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

COMBOS = {
    "baseline": BASELINE,
    "kup": [f if f != "CNTN30" else "KUP" for f in BASELINE],
    "vstd60": [f if f != "BETA60" else "VSTD60" for f in BASELINE],
    "diverse": [
        "GAP723", "PANIC_BUY",
        "QTLD60", "LOW0", "ROC60", "VSUMP60", "KUP", "VSUMD60",
        "MIN20", "MIN30",
        "CORR10", "KLEN", "CORD10",
        "MIN5", "MIN10", "MIN60",
        "VSUMN60", "MA60", "CORD20", "STD10",
        "IMIN60", "VMA60", "SUMN30", "VOL_MA_MKT",
    ],
    "top23_strong": json.loads((DATA_DIR / "top23_strong.json").read_text(encoding="utf-8")),
}


def extract_metrics(data: dict) -> dict:
    """通过位置提取指标（服务端中文键编码异常，但顺序稳定）。"""
    m = data.get("metrics", {})
    keys = list(m.keys())
    # 顺序：总收益、年化收益、年化波动、夏普、最大回撤、最大回撤时间、胜率、交易日数、initial_value、Alpha(年化)、Beta、IF总收益
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
    # 服务端返回中文键值可能是 GBK 编码，需要显式解码
    for enc in ("utf-8", "gbk", "gb2312"):
        try:
            text = r.content.decode(enc)
            return json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError):
            continue
    # 兜底：按 httpx 默认
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

        out_path = DATA_DIR / "quantile_screen_results.json"
        out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n结果已保存: {out_path}")


if __name__ == "__main__":
    asyncio.run(main())
