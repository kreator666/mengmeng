# -*- coding: utf-8 -*-
"""
v11_core 策略扫描器 核心模块

Markethon 天梯历史最高分组合（standard_score 47.07，submission: darkspell-v11_core）
横向移植到 Gate.io 永续合约：对每个合约计算 11 个因子的最新值，
做截面 z-score 加权合成打分，按分数排序输出多空候选。

因子定义（qlib Alpha158 内置 + 自定义）：
  ROC60      = $close / Ref($close, 60)
  MA60       = Mean($close, 60) / $close
  STD10      = Std($close, 10) / $close
  BETA60     = Slope($close, 60) / $close
  CORR10     = Corr($close, Log($volume+1), 10)
  VMA60      = Mean($volume, 60) / $volume
  LOW0       = $low / Ref($low, 1)
  GAP723     = ($open - Ref($close, 1)) / Ref($close, 1)
  PANIC_BUY  = ($low - Min($open,$close)) / ($high-$low) * ($volume / Mean($volume, 5))
  VSUMN60    = Sum(Greater(Ref($volume,1)-$volume, 0), 60) / Sum(Abs($volume-Ref($volume,1)), 60)
  VSUMP60    = Sum(Greater($volume-Ref($volume,1), 0), 60) / Sum(Abs($volume-Ref($volume,1)), 60)
"""
import asyncio
import math
import statistics

import httpx

from app.core.bottom_trend_scanner import _gate_get_contracts, _gate_get_klines

# ---------------------------------------------------------------------------
# 策略参数（来自 leaderboard_submit_v11_core.json）
# ---------------------------------------------------------------------------
STRATEGY_NAME = "v11_core"
LEADERBOARD_SCORE = 47.07

V11_WEIGHTS = {
    "ROC60": 0.121518,
    "MA60": 0.099901,
    "STD10": -0.116911,
    "BETA60": -0.065488,
    "CORR10": -0.202910,
    "VMA60": 0.190552,
    "LOW0": 0.396746,
    "GAP723": 0.251597,
    "PANIC_BUY": 0.242214,
    "VSUMN60": 0.212557,
    "VSUMP60": -0.212556,
}

MIN_BARS = 80  # VSUMN60/VSUMP60/ROC60 等需要 61 根，留有余量
EPS = 1e-12


# ---------------------------------------------------------------------------
# 单合约因子计算
# ---------------------------------------------------------------------------

def _slope(y: list[float]) -> float:
    """最小二乘拟合斜率（每 bar 变化量）。"""
    n = len(y)
    sx = n * (n - 1) / 2
    sxx = n * (n - 1) * (2 * n - 1) / 6
    sy = sum(y)
    sxy = sum(i * v for i, v in enumerate(y))
    denom = n * sxx - sx * sx
    return (n * sxy - sx * sy) / denom if denom else 0.0


def _corr(x: list[float], y: list[float]) -> float:
    n = len(x)
    mx = sum(x) / n
    my = sum(y) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(x, y))
    vx = sum((a - mx) ** 2 for a in x)
    vy = sum((b - my) ** 2 for b in y)
    if vx <= 0 or vy <= 0:
        return 0.0
    return cov / math.sqrt(vx * vy)


def _vsum(closes_or_vols: list[float], n: int, positive: bool) -> float | None:
    """VSUMP/VSUMN：过去 n 根 bar 中成交量增/减幅度占比。"""
    seg = closes_or_vols[-(n + 1):]
    if len(seg) < n + 1:
        return None
    up = down = 0.0
    for i in range(1, len(seg)):
        d = seg[i] - seg[i - 1]
        if d > 0:
            up += d
        else:
            down -= d
    total = up + down
    if total <= 0:
        return None
    return (up if positive else down) / total


def compute_factors(klines: list[dict]) -> dict | None:
    """从 K 线列表计算 v11_core 的 11 个因子最新值；数据不足返回 None。"""
    if not klines or len(klines) < MIN_BARS:
        return None

    closes = [k["close"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    opens = [k["open"] for k in klines]
    vols = [k["vol"] for k in klines]

    cur = closes[-1]
    if cur <= 0:
        return None

    try:
        roc60 = closes[-1] / closes[-61]
        ma60 = sum(closes[-60:]) / 60 / cur
        std10 = statistics.stdev(closes[-10:]) / cur
        beta60 = _slope(closes[-60:]) / cur
        corr10 = _corr(closes[-10:], [math.log(v + 1) for v in vols[-10:]])
        vma60 = sum(vols[-60:]) / 60 / (vols[-1] + EPS)
        low0 = lows[-1] / lows[-2]
        gap723 = (opens[-1] - closes[-2]) / closes[-2]

        rng = highs[-1] - lows[-1]
        lower_shadow = (lows[-1] - min(opens[-1], closes[-1])) / rng if rng > 0 else 0.0
        vol_ratio5 = vols[-1] / (sum(vols[-5:]) / 5) if sum(vols[-5:]) > 0 else 0.0
        panic_buy = lower_shadow * vol_ratio5

        vsumn60 = _vsum(vols, 60, positive=False)
        vsump60 = _vsum(vols, 60, positive=True)
    except (IndexError, ZeroDivisionError, statistics.StatisticsError):
        return None

    if vsumn60 is None or vsump60 is None:
        return None

    factors = {
        "ROC60": roc60,
        "MA60": ma60,
        "STD10": std10,
        "BETA60": beta60,
        "CORR10": corr10,
        "VMA60": vma60,
        "LOW0": low0,
        "GAP723": gap723,
        "PANIC_BUY": panic_buy,
        "VSUMN60": vsumn60,
        "VSUMP60": vsump60,
    }
    if any(not math.isfinite(v) for v in factors.values()):
        return None
    return factors


# ---------------------------------------------------------------------------
# 截面合成打分
# ---------------------------------------------------------------------------

def _zscore(values: list[float]) -> list[float]:
    n = len(values)
    if n < 2:
        return [0.0] * n
    mu = sum(values) / n
    sd = statistics.stdev(values)
    if sd <= 0:
        return [0.0] * n
    return [(v - mu) / sd for v in values]


def _direction(score: float) -> str:
    if score >= 1.0:
        return "强烈做多"
    if score >= 0.3:
        return "偏多"
    if score <= -1.0:
        return "强烈做空"
    if score <= -0.3:
        return "偏空"
    return "中性"


def composite_scan(rows: list[dict]) -> dict:
    """对全部合约的因子值做截面 z-score 加权合成，返回排序结果。"""
    factor_names = list(V11_WEIGHTS.keys())
    z_scores = {}
    factor_stats = {}
    for name in factor_names:
        vals = [r["factors"][name] for r in rows]
        z = _zscore(vals)
        z_scores[name] = z
        mu = sum(vals) / len(vals)
        sd = statistics.stdev(vals) if len(vals) > 1 else 0.0
        factor_stats[name] = {"mean": mu, "std": sd}

    for i, r in enumerate(rows):
        z = {name: round(z_scores[name][i], 4) for name in factor_names}
        score = sum(V11_WEIGHTS[name] * z[name] for name in factor_names)
        r["z"] = z
        r["score"] = round(score, 4)
        r["direction"] = _direction(score)

    ranking = sorted(rows, key=lambda x: -x["score"])
    for i, r in enumerate(ranking):
        r["rank"] = i + 1
    return {"ranking": ranking, "factor_stats": factor_stats}


# ---------------------------------------------------------------------------
# Gate.io 永续合约扫描
# ---------------------------------------------------------------------------

async def scan_gate_futures(progress_callback=None) -> dict:
    """扫描 Gate.io 永续合约（范围与底部趋势扫描器一致）。"""
    async with httpx.AsyncClient() as client:
        contracts = await _gate_get_contracts(client)
        total = len(contracts)

        rows = []
        done = 0
        sem = asyncio.Semaphore(20)

        async def _scan_one(c):
            nonlocal done
            async with sem:
                klines = await _gate_get_klines(client, c)
                factors = compute_factors(klines)
                if factors:
                    rows.append({
                        "pair": c,
                        "price": round(klines[-1]["close"], 6),
                        "factors": {k: round(v, 6) for k, v in factors.items()},
                    })
                done += 1
                if progress_callback and (done % 100 == 0 or done == total):
                    await progress_callback(done, total, len(rows))

        await asyncio.gather(*[_scan_one(c) for c in contracts])

    return _build_output(contracts, rows)


def _build_output(contracts: list, rows: list) -> dict:
    from datetime import datetime

    combined = composite_scan(rows) if rows else {"ranking": [], "factor_stats": {}}
    ranking = combined["ranking"]

    top_long = [r for r in ranking if r["score"] > 0][:30]
    top_short = [r for r in ranking if r["score"] < 0][-30:][::-1]

    return {
        "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "exchange": "gate_futures",
        "strategy": STRATEGY_NAME,
        "leaderboard_score": LEADERBOARD_SCORE,
        "total_pairs": len(contracts),
        "scanned": len(rows),
        "weights": V11_WEIGHTS,
        "factor_stats": combined["factor_stats"],
        "ranking": ranking,
        "top_long": top_long,
        "top_short": top_short,
        "min_bars": MIN_BARS,
    }
