# -*- coding: utf-8 -*-
"""
Gate.io 永续合约 底部趋势双策略综合扫描器
策略1（横盘底部）：AR<=1.008  AND  跌幅>=50%  → 两维度独立过滤
策略2（趋势追涨）：ADX>=15    AND  涨幅>=5%   AND  跌幅10-85%  → 等级评分
"""
import requests, json, time, statistics, sys, argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from collections import Counter

sys.stdout.reconfigure(encoding='utf-8')

GATE = "https://api.gateio.ws/api/v4"
OUT_FILE = "gate_futures_scan_results.json"

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

def get_klines(contract, interval="1h", limit=500):
    try:
        r = requests.get(f"{GATE}/futures/usdt/candlesticks",
                         params={"contract": contract, "interval": interval, "limit": limit}, timeout=10)
        if r.status_code != 200:
            return None
        raw = r.json()
        if not raw:
            return None
        out = []
        for k in raw:
            out.append({
                "ts":    int(k["t"]),
                "open":  float(k["o"]),
                "high":  float(k["h"]),
                "low":   float(k["l"]),
                "close": float(k["c"]),
                "vol":   float(k["v"]),
            })
        out.sort(key=lambda x: x["ts"])
        return out
    except Exception:
        return None

def ma(series, n):
    return [None if i < n-1 else sum(series[i-n+1:i+1])/n for i in range(len(series))]

def adx_proxy(highs, lows, closes, window=14):
    result = [None] * (window + 1)
    pdm_l, mdm_l, tr_l = [], [], []
    for i in range(1, len(highs)):
        hd = highs[i] - highs[i-1]
        ld = lows[i-1] - lows[i]
        tr = max(highs[i]-lows[i], abs(highs[i]-closes[i-1]), abs(lows[i]-closes[i-1]))
        pdm_l.append(hd if hd > ld and hd > 0 else 0)
        mdm_l.append(ld if ld > hd and ld > 0 else 0)
        tr_l.append(tr)
    if len(tr_l) < window:
        return result
    ss = sum(tr_l[:window]); ps = sum(pdm_l[:window]); ms = sum(mdm_l[:window])
    for i in range(window, len(highs)):
        ss = (ss*(window-1) + tr_l[i-1]) / window
        ps = (ps*(window-1) + pdm_l[i-1]) / window
        ms = (ms*(window-1) + mdm_l[i-1]) / window
        result.append(abs(ps - ms) / ss * 100 if ss > 0 else 0)
    return result

def get_all_contracts():
    r = requests.get(f"{GATE}/futures/usdt/contracts", timeout=20)
    contracts = r.json()
    LEV_SUFFIXES = ("3S", "3L", "5S", "5L", "10S", "10L")
    out = []
    for c in contracts:
        name = c.get("name", "")
        if c.get("in_delisting"):
            continue
        if any(name.replace("_USDT", "").endswith(s) for s in LEV_SUFFIXES):
            continue
        out.append(name)
    return out

def calc(contract):
    klines = get_klines(contract, "1h", 500)
    if not klines or len(klines) < PARAMS["min_bars"]:
        return None

    closes = [k["close"] for k in klines]
    highs  = [k["high"]  for k in klines]
    lows   = [k["low"]   for k in klines]
    vols   = [k["vol"]   for k in klines]
    ts     = [k["ts"]    for k in klines]

    ath       = max(closes)
    cur       = closes[-1]
    ath_drop  = (ath - cur) / ath * 100 if ath > 0 else 0
    ath_time  = ts[closes.index(ath)]
    atl       = min(closes)
    atl_time  = ts[closes.index(atl)]
    atl_gain  = (cur - atl) / atl * 100 if atl > 0 else 0

    ma5  = ma(closes, 5)
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

        c20 = closes[i-19:i+1]
        m_c = sum(c20) / 20
        cv  = statistics.stdev(c20) / m_c if m_c > 0 else None
        if cv is None or cv > PARAMS["cv_max"] or cv < PARAMS["cv_min"]:
            continue

        v20 = vols[i-19:i]
        v20_sum = sum(v20) if v20 else 0
        vr  = vols[i] / (v20_sum/20) if v20_sum > 0 else 0
        gain5  = (closes[i] - closes[i-5]) / closes[i-5] * 100 if i >= 5 and closes[i-5] > 0 else 0
        gain20 = (closes[i] - closes[i-20]) / closes[i-20] * 100 if i >= 20 and closes[i-20] > 0 else 0

        bull_align   = ma5[i] > ma10[i] > ma20[i]
        bull_partial = ma5[i] > ma20[i]

        m5v  = ma5[i]  if ma5[i]  else 0
        m10v = ma10[i] if ma10[i] else 0
        m20v = ma20[i] if ma20[i] else 0
        ar   = max(m5v, m10v, m20v) / min(m5v, m10v, m20v) if min(m5v, m10v, m20v) > 0 else None

        score = 0
        if adx >= PARAMS["adx_strong"]: score += 3
        elif adx >= 20:                 score += 2
        elif adx >= PARAMS["adx_min"]:  score += 1
        if bull_align:                  score += 2
        elif bull_partial:              score += 1
        if gain20 >= 20:                score += 2
        elif gain20 >= 5:               score += 1
        if vr >= 2.0:                   score += 1

        if   adx >= 30 and bull_align:     grade = "AAA"
        elif adx >= 30:                    grade = "AA"
        elif adx >= 20 and bull_align:     grade = "A"
        elif adx >= 20:                    grade = "B"
        elif adx >= 15 and bull_partial:   grade = "C"
        else:                              grade = "D"

        if   ath_drop < 30:  zone = "A"
        elif ath_drop < 50:  zone = "B"
        elif ath_drop < 70:  zone = "C"
        else:                zone = "D"

        if gain20 > 10 and bull_align:   status = "拉升中"
        elif gain20 > 0 and adx >= 20:   status = "启动中"
        elif ar and ar <= 1.008:         status = "横盘蓄力"
        elif bull_align:                  status = "多头"
        else:                             status = "蓄力/回调"

        if (best is None or score > best["score"]
            or (score == best["score"] and adx > best["adx"])):
            best = {
                "adx":        round(adx, 2),
                "cv":         round(cv, 5),
                "vr":         round(vr, 2),
                "gain5":      round(gain5, 2),
                "gain20":     round(gain20, 2),
                "ath_drop":   round(ath_drop, 2),
                "atl_gain":   round(atl_gain, 2),
                "bull_align": bull_align,
                "bull_partial": bull_partial,
                "score":      score,
                "grade":      grade,
                "zone":       zone,
                "ar":         round(ar, 5) if ar else None,
                "status":     status,
                "ath":        round(ath, 6),
                "atl":        round(atl, 6),
                "ath_time":   datetime.fromtimestamp(ath_time).strftime("%m-%d"),
                "atl_time":   datetime.fromtimestamp(atl_time).strftime("%m-%d"),
                "cur":        round(cur, 6),
                "ts":         datetime.fromtimestamp(ts[i]).strftime("%m-%d %H:%M"),
            }

    if best and ath_drop >= PARAMS["ath_drop_min"] and ath_drop <= PARAMS["ath_drop_max"]:
        best["pair"] = contract
        return best
    return None

def main():
    parser = argparse.ArgumentParser(description="Gate.io 永续合约扫描器")
    parser.add_argument("--strategy", choices=["bottom", "trend", "both"], default="both", help="扫描策略")
    parser.add_argument("--output", default=OUT_FILE, help="输出文件路径")
    args = parser.parse_args()

    t0 = time.time()
    print("======================================================================")
    print("  Gate.io 永续合约 底部趋势双策略综合扫描器")
    print("  策略1：横盘底部（AR<=1.008 AND 跌幅>=50%）")
    print("  策略2：趋势追涨（ADX>=15 AND 涨幅>=5% AND 跌幅10-85%）")
    print("======================================================================")

    contracts = get_all_contracts()
    print(f"\n  Gate USDT永续合约: {len(contracts)} 个（已排除退市/杠杆代币）")
    print(f"  并发线程: 20")
    print(f"  ──────────────────────────────────────────────────────────────")

    results = []
    done = 0

    with ThreadPoolExecutor(max_workers=20) as ex:
        futures = {ex.submit(calc, c): c for c in contracts}
        for f in as_completed(futures):
            done += 1
            r = f.result()
            if r:
                results.append(r)
            if done % 100 == 0 or done == len(contracts):
                elapsed = time.time() - t0
                speed = done / elapsed
                eta = (len(contracts) - done) / speed
                print(f"  [{done}/{len(contracts)}] {len(results)}个候选  {speed:.1f}个/秒  ETA:{eta:.0f}秒")

    trend_candidates = [r for r in results if r["gain20"] >= PARAMS["gain20_min"]]
    bottom_candidates = [r for r in results
                         if r.get("ar") and r["ar"] <= PARAMS["ar_max"]
                         and r["ath_drop"] >= 50.0]

    elapsed = time.time() - t0
    grades = Counter(r["grade"] for r in results)
    zones = {"A":[],"B":[],"C":[],"D":[]}
    for r in results:
        z = r.get("zone","?")
        if z in zones: zones[z].append(r)

    print(f"\n\n======================================================================")
    print(f"  扫描完成！共 {len(results)} 个趋势候选  耗时 {elapsed:.0f}秒")
    print(f"======================================================================")

    print(f"\n  趋势等级分布：")
    for g in ["AAA","AA","A","B","C","D"]:
        if grades.get(g): print(f"    {g}: {grades[g]} 个")

    print(f"\n  按ATH跌幅分层：")
    for z, lbl in [("A","浅回调 10-30%"),("B","中回调 30-50%"),("C","深回调 50-70%"),("D","超跌反弹 70-85%")]:
        print(f"    {z}区({lbl}): {len(zones[z])} 个")

    print(f"\n  【A区】浅回调 TOP10：")
    for r in sorted(zones["A"], key=lambda x: (-x["score"], -x["adx"]))[:10]:
        print(f"    {r['pair']:<20} 得分={r['score']} ADX={r['adx']:>5.1f} 涨幅={r['gain20']:>+6.1f}% {r['grade']} {r['status']}")

    print(f"\n  【B区】中回调 TOP10：")
    for r in sorted(zones["B"], key=lambda x: (-x["score"], -x["adx"]))[:10]:
        ar_str = f"AR={r['ar']:.5f}" if r.get("ar") else ""
        print(f"    {r['pair']:<20} 跌幅={r['ath_drop']:>5.1f}% ADX={r['adx']:>5.1f} 涨幅={r['gain20']:>+6.1f}% {r['grade']} {ar_str}")

    print(f"\n  【C+D区】深回调/超跌：")
    cd = sorted(zones["C"] + zones["D"], key=lambda x: -x["ath_drop"])
    for r in cd[:10]:
        bull = "多头" if r["bull_align"] else ("偏多" if r["bull_partial"] else "空")
        ar_str = f"AR={r['ar']:.5f}" if r.get("ar") else ""
        print(f"    {r['pair']:<20} 跌幅={r['ath_drop']:>5.1f}% ADX={r['adx']:>5.1f} 涨幅={r['gain20']:>+6.1f}% {r['grade']} {bull} {ar_str}")

    print(f"\n  ⭐ 横盘底部候选（AR<=1.008 AND 跌幅>=50%）共 {len(bottom_candidates)} 个")
    bottom_sorted = sorted(bottom_candidates, key=lambda x: (x.get("ar", 999), -x["ath_drop"]))
    for i, r in enumerate(bottom_sorted[:10]):
        bull = "多头" if r["bull_align"] else ("偏多" if r["bull_partial"] else "空")
        print(f"    {r['pair']:<20} AR={r['ar']:.5f} 跌幅={r['ath_drop']:>5.1f}% ADX={r['adx']:>5.1f} {bull} {r['status']}")

    out_data = {
        "scan_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "exchange": "gate_futures",
        "total_pairs": len(contracts),
        "all_candidates": results,
        "trend_candidates": trend_candidates,
        "bottom_candidates": bottom_candidates,
        "grades": dict(grades),
        "zones": {z: len(v) for z, v in zones.items()},
        "params": PARAMS,
    }
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(out_data, f, ensure_ascii=False, indent=2)

    print(f"\n  结果已保存: {args.output}")
    print(f"  总耗时: {elapsed:.0f}秒  速度: {len(contracts)/elapsed:.1f}个/秒")

if __name__ == "__main__":
    main()
