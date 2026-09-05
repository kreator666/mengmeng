# -*- coding: utf-8 -*-
"""
底部趋势双策略扫描器 核心模块
策略1（横盘底部）：AR<=1.008  AND  跌幅>=50%
策略2（趋势追涨）：ADX>=15    AND  涨幅>=5%   AND  跌幅10-85%
"""
import asyncio
import statistics
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from collections import Counter

import httpx

# ---------------------------------------------------------------------------
# 参数
# ---------------------------------------------------------------------------
PARAMS = {
    "min_bars": 300,
    "ath_drop_min": 10.0,
    "ath_drop_max": 85.0,
    "adx_min": 15.0,
    "adx_strong": 30.0,
    "gain20_min": 5.0,
    "vr_min": 1.5,
    "cv_min": 0.001,
    "cv_max": 0.08,
    "ar_max": 1.008,
    "ar_bottom_max": 1.050,
}

LEV_SUFFIXES = ("3S", "3L", "5S", "5L", "10S", "10L")

# ---------------------------------------------------------------------------
# 技术指标
# ---------------------------------------------------------------------------

def ma(series, n):
    return [None if i < n - 1 else sum(series[i - n + 1 : i + 1]) / n for i in range(len(series))]


def adx_proxy(highs, lows, closes, window=14):
    result = [None] * (window + 1)
    pdm_l, mdm_l, tr_l = [], [], []
    for i in range(1, len(highs)):
        hd = highs[i] - highs[i - 1]
        ld = lows[i - 1] - lows[i]
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        pdm_l.append(hd if hd > ld and hd > 0 else 0)
        mdm_l.append(ld if ld > hd and ld > 0 else 0)
        tr_l.append(tr)
    if len(tr_l) < window:
        return result
    ss = sum(tr_l[:window])
    ps = sum(pdm_l[:window])
    ms = sum(mdm_l[:window])
    for i in range(window, len(highs)):
        ss = (ss * (window - 1) + tr_l[i - 1]) / window
        ps = (ps * (window - 1) + pdm_l[i - 1]) / window
        ms = (ms * (window - 1) + mdm_l[i - 1]) / window
        result.append(abs(ps - ms) / ss * 100 if ss > 0 else 0)
    return result


def calc_score(adx, bull_align, bull_partial, gain20, vr):
    score = 0
    if adx >= PARAMS["adx_strong"]:
        score += 3
    elif adx >= 20:
        score += 2
    elif adx >= PARAMS["adx_min"]:
        score += 1
    if bull_align:
        score += 2
    elif bull_partial:
        score += 1
    if gain20 >= 20:
        score += 2
    elif gain20 >= 5:
        score += 1
    if vr >= 2.0:
        score += 1
    return score


def calc_grade(adx, bull_align, bull_partial):
    if adx >= 30 and bull_align:
        return "AAA"
    elif adx >= 30:
        return "AA"
    elif adx >= 20 and bull_align:
        return "A"
    elif adx >= 20:
        return "B"
    elif adx >= 15 and bull_partial:
        return "C"
    else:
        return "D"


def calc_zone(ath_drop):
    if ath_drop < 30:
        return "A"
    elif ath_drop < 50:
        return "B"
    elif ath_drop < 70:
        return "C"
    else:
        return "D"


# ---------------------------------------------------------------------------
# 单币种计算
# ---------------------------------------------------------------------------

def _calc_from_klines(klines):
    """从 K 线列表计算单个币种的结果（同步，用于线程池）"""
    if not klines or len(klines) < PARAMS["min_bars"]:
        return None

    closes = [k["close"] for k in klines]
    highs = [k["high"] for k in klines]
    lows = [k["low"] for k in klines]
    vols = [k["vol"] for k in klines]
    ts = [k["ts"] for k in klines]

    ath = max(closes)
    cur = closes[-1]
    ath_drop = (ath - cur) / ath * 100 if ath > 0 else 0
    ath_time = ts[closes.index(ath)]
    atl = min(closes)
    atl_time = ts[closes.index(atl)]
    atl_gain = (cur - atl) / atl * 100 if atl > 0 else 0

    ma5 = ma(closes, 5)
    ma10 = ma(closes, 10)
    ma20 = ma(closes, 20)
    adx_vals = adx_proxy(highs, lows, closes, 14)

    best = None
    start = max(50, len(klines) - 50)
    for i in range(start, len(klines)):
        if ma5[i] is None:
            continue
        adx = adx_vals[i] if i < len(adx_vals) else None
        if adx is None or adx < PARAMS["adx_min"]:
            continue

        c20 = closes[i - 19 : i + 1]
        m_c = sum(c20) / 20
        cv = statistics.stdev(c20) / m_c if m_c > 0 else None
        if cv is None or cv > PARAMS["cv_max"] or cv < PARAMS["cv_min"]:
            continue

        v20 = vols[i - 19 : i]
        v20_sum = sum(v20) if v20 else 0
        vr = vols[i] / (v20_sum / 20) if v20_sum > 0 else 0
        gain5 = (closes[i] - closes[i - 5]) / closes[i - 5] * 100 if i >= 5 and closes[i - 5] > 0 else 0
        gain20 = (closes[i] - closes[i - 20]) / closes[i - 20] * 100 if i >= 20 and closes[i - 20] > 0 else 0

        bull_align = ma5[i] > ma10[i] > ma20[i]
        bull_partial = ma5[i] > ma20[i]

        m5v = ma5[i] if ma5[i] else 0
        m10v = ma10[i] if ma10[i] else 0
        m20v = ma20[i] if ma20[i] else 0
        ar = max(m5v, m10v, m20v) / min(m5v, m10v, m20v) if min(m5v, m10v, m20v) > 0 else None

        score = calc_score(adx, bull_align, bull_partial, gain20, vr)
        grade = calc_grade(adx, bull_align, bull_partial)
        zone = calc_zone(ath_drop)

        if gain20 > 10 and bull_align:
            status = "拉升中"
        elif gain20 > 0 and adx >= 20:
            status = "启动中"
        elif ar and ar <= 1.008:
            status = "横盘蓄力"
        elif bull_align:
            status = "多头"
        else:
            status = "蓄力/回调"

        if best is None or score > best["score"] or (score == best["score"] and adx > best["adx"]):
            best = {
                "adx": round(adx, 2),
                "cv": round(cv, 5),
                "vr": round(vr, 2),
                "gain5": round(gain5, 2),
                "gain20": round(gain20, 2),
                "ath_drop": round(ath_drop, 2),
                "atl_gain": round(atl_gain, 2),
                "bull_align": bull_align,
                "bull_partial": bull_partial,
                "score": score,
                "grade": grade,
                "zone": zone,
                "ar": round(ar, 5) if ar else None,
                "status": status,
                "ath": round(ath, 6),
                "atl": round(atl, 6),
                "ath_time": datetime.fromtimestamp(ath_time).strftime("%m-%d") if ath_time < 1e12 else datetime.fromtimestamp(ath_time / 1000).strftime("%m-%d"),
                "atl_time": datetime.fromtimestamp(atl_time).strftime("%m-%d") if atl_time < 1e12 else datetime.fromtimestamp(atl_time / 1000).strftime("%m-%d"),
                "cur": round(cur, 6),
                "ts": datetime.fromtimestamp(ts[i]).strftime("%m-%d %H:%M") if ts[i] < 1e12 else datetime.fromtimestamp(ts[i] / 1000).strftime("%m-%d %H:%M"),
            }

    if best and ath_drop >= PARAMS["ath_drop_min"] and ath_drop <= PARAMS["ath_drop_max"]:
        return best
    return None


# ---------------------------------------------------------------------------
# Gate.io 永续合约扫描
# ---------------------------------------------------------------------------

async def _gate_get_contracts(client: httpx.AsyncClient) -> list[str]:
    r = await client.get("https://api.gateio.ws/api/v4/futures/usdt/contracts", timeout=20)
    contracts = r.json()
    out = []
    for c in contracts:
        name = c.get("name", "")
        if c.get("in_delisting"):
            continue
        if any(name.replace("_USDT", "").endswith(s) for s in LEV_SUFFIXES):
            continue
        out.append(name)
    return out


async def _gate_get_klines(client: httpx.AsyncClient, contract: str) -> list[dict] | None:
    try:
        r = await client.get(
            "https://api.gateio.ws/api/v4/futures/usdt/candlesticks",
            params={"contract": contract, "interval": "1h", "limit": 500},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        raw = r.json()
        if not raw:
            return None
        out = []
        for k in raw:
            out.append({
                "ts": int(k["t"]),
                "open": float(k["o"]),
                "high": float(k["h"]),
                "low": float(k["l"]),
                "close": float(k["c"]),
                "vol": float(k["v"]),
            })
        out.sort(key=lambda x: x["ts"])
        return out
    except Exception:
        return None


async def scan_gate_futures(progress_callback=None) -> dict:
    """扫描 Gate.io 永续合约"""
    async with httpx.AsyncClient() as client:
        contracts = await _gate_get_contracts(client)
        total = len(contracts)

        results = []
        done = 0
        sem = asyncio.Semaphore(20)

        async def _scan_one(c):
            nonlocal done
            async with sem:
                klines = await _gate_get_klines(client, c)
                r = _calc_from_klines(klines)
                if r:
                    r["pair"] = c
                    results.append(r)
                done += 1
                if progress_callback and (done % 100 == 0 or done == total):
                    await progress_callback(done, total, len(results))

        await asyncio.gather(*[_scan_one(c) for c in contracts])

    return _build_output("gate_futures", contracts, results)


# ---------------------------------------------------------------------------
# Binance 现货扫描
# ---------------------------------------------------------------------------

async def _binance_get_pairs(client: httpx.AsyncClient) -> list[str]:
    r = await client.get("https://api.binance.com/api/v3/exchangeInfo", timeout=20)
    data = r.json()
    out = []
    for s in data.get("symbols", []):
        if s.get("status") != "TRADING":
            continue
        symbol = s.get("symbol", "")
        if not symbol.endswith("USDT"):
            continue
        if any(symbol.endswith(suf + "USDT") for suf in LEV_SUFFIXES):
            continue
        out.append(symbol)
    return out


async def _binance_get_klines(client: httpx.AsyncClient, symbol: str) -> list[dict] | None:
    try:
        r = await client.get(
            "https://api.binance.com/api/v3/klines",
            params={"symbol": symbol, "interval": "1h", "limit": 500},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        raw = r.json()
        if not raw:
            return None
        out = []
        for k in raw:
            out.append({
                "ts": int(k[0]),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "vol": float(k[5]),
            })
        return out
    except Exception:
        return None


async def scan_binance_spot(progress_callback=None) -> dict:
    """扫描 Binance 现货"""
    async with httpx.AsyncClient() as client:
        pairs = await _binance_get_pairs(client)
        total = len(pairs)

        results = []
        sem = asyncio.Semaphore(10)

        async def _scan_one(sym):
            async with sem:
                klines = await _binance_get_klines(client, sym)
                r = _calc_from_klines(klines)
                if r:
                    r["pair"] = sym
                    results.append(r)

        await asyncio.gather(*[_scan_one(p) for p in pairs])

    return _build_output("binance_spot", pairs, results)


# ---------------------------------------------------------------------------
# OKX 现货扫描
# ---------------------------------------------------------------------------

async def _okx_get_pairs(client: httpx.AsyncClient) -> list[str]:
    r = await client.get("https://www.okx.com/api/v5/market/tickers?instType=SPOT", timeout=20)
    data = r.json()
    out = []
    for item in data.get("data", []):
        inst = item.get("instId", "")
        if not inst.endswith("-USDT"):
            continue
        base = inst.replace("-USDT", "")
        if any(base.endswith(s) for s in LEV_SUFFIXES):
            continue
        out.append(inst)
    return out


async def _okx_get_klines(client: httpx.AsyncClient, inst: str) -> list[dict] | None:
    try:
        r = await client.get(
            "https://www.okx.com/api/v5/market/candles",
            params={"instId": inst, "bar": "1H", "limit": 300},
            timeout=10,
        )
        if r.status_code != 200:
            return None
        raw = r.json().get("data", [])
        if not raw:
            return None
        out = []
        for k in raw:
            out.append({
                "ts": int(k[0]),
                "open": float(k[1]),
                "high": float(k[2]),
                "low": float(k[3]),
                "close": float(k[4]),
                "vol": float(k[5]),
            })
        out.reverse()
        return out
    except Exception:
        return None


async def scan_okx_spot(progress_callback=None) -> dict:
    """扫描 OKX 现货"""
    async with httpx.AsyncClient() as client:
        pairs = await _okx_get_pairs(client)
        total = len(pairs)

        results = []
        sem = asyncio.Semaphore(10)

        async def _scan_one(inst):
            async with sem:
                klines = await _okx_get_klines(client, inst)
                r = _calc_from_klines(klines)
                if r:
                    r["pair"] = inst
                    results.append(r)

        await asyncio.gather(*[_scan_one(p) for p in pairs])

    return _build_output("okx_spot", pairs, results)


# ---------------------------------------------------------------------------
# 结果汇总
# ---------------------------------------------------------------------------

def _build_output(exchange: str, pairs: list, results: list) -> dict:
    trend_candidates = [r for r in results if r["gain20"] >= PARAMS["gain20_min"]]
    bottom_candidates = [
        r for r in results
        if r.get("ar") and r["ar"] <= PARAMS["ar_max"] and r["ath_drop"] >= 50.0
    ]

    grades = Counter(r["grade"] for r in results)
    zones = {"A": [], "B": [], "C": [], "D": []}
    for r in results:
        z = r.get("zone", "?")
        if z in zones:
            zones[z].append(r)

    # 按 zone 排序后的 top
    top_by_zone = {}
    for z in ["A", "B", "C", "D"]:
        top_by_zone[z] = sorted(zones[z], key=lambda x: (-x["score"], -x["adx"]))[:10]

    return {
        "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "exchange": exchange,
        "total_pairs": len(pairs),
        "all_candidates": sorted(results, key=lambda x: (-x["score"], -x["adx"])),
        "trend_candidates": trend_candidates,
        "bottom_candidates": sorted(bottom_candidates, key=lambda x: (x.get("ar", 999), -x["ath_drop"])),
        "grades": dict(grades),
        "zones": {z: len(v) for z, v in zones.items()},
        "top_by_zone": top_by_zone,
        "params": PARAMS,
    }


# ---------------------------------------------------------------------------
# 路由映射
# ---------------------------------------------------------------------------

SCANNERS = {
    "gate": scan_gate_futures,
    "binance": scan_binance_spot,
    "okx": scan_okx_spot,
}
