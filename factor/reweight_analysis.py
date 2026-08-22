"""
重新分析因子权重
目标：AR(均线粘连) vs ATH跌幅，到底应该各占多少？
"""
import json

with open(r'C:\Users\tiger\.qclaw\workspace\scan_results.json', encoding='utf-8') as f:
    data = json.load(f)

results = data['results']

# ─── 排除稳定币（CV < 0.001 即为稳定币锚定币）───
stable_coins = {r['symbol'] for r in results if r['cv'] < 0.001 and r['ath_drop'] < 1.0}
print(f"稳定币/锚定币: {stable_coins}\n")

filtered = [r for r in results
            if r['ath_drop'] >= 20   # 先放宽跌幅看全貌
            and r['cv'] >= 0.001    # 排除稳定币
            and r['ar'] <= 1.050    # 先排除明显非横盘
           ]

print(f"满足 AR<=1.050 且 CV>=0.001 且 跌幅>=20% 的标的: {len(filtered)} 个\n")

# ─── 模拟不同权重方案 ───────────────────────────────────────────────────
# 方案A：当前权重（ATH_drop占20%）
# 方案B：ATH改为过滤条件，AR权重提高
# 方案C：ATH+AR双重过滤，更细粒度评分

def calc_score_vA(r):
    """当前方案：ATH_drop参与评分"""
    ar_sc  = max(0, 5 - (r['ar'] - 1.000) * 500)
    cv_sc  = max(0, 5 - r['cv'] * 500)
    adx_sc = max(0, 5 - r['adx'] / 10 * 5)
    drop_sc= max(0, min(5, (r['ath_drop'] - 50) / 50 * 5))  # 50%=0分, 100%=5分
    vol_sc = max(0, min(5, r['vol_ratio']))
    bt_sc  = 5 if r['breakout'] else 0
    return ar_sc + cv_sc + adx_sc + drop_sc + vol_sc + bt_sc

def calc_score_vB(r):
    """修订方案：ATH改为硬过滤，AR/CV/ADX提权"""
    drop_pass = r['ath_drop'] >= 50   # 硬过滤：跌幅>=50%
    ar_sc  = max(0, 5 - (r['ar'] - 1.000) * 400)   # 权重不变但门槛放宽
    cv_sc  = max(0, 5 - r['cv'] * 400)
    adx_sc = max(0, 5 - r['adx'] / 8 * 5)
    vol_sc = max(0, min(5, r['vol_ratio']))
    bt_sc  = 5 if r['breakout'] else 0
    total = ar_sc + cv_sc + adx_sc + vol_sc + bt_sc
    return (total, drop_pass)

def calc_score_vC(r):
    """双重过滤：AR<=1.010 + 跌幅>=60%"""
    ar_pass  = r['ar'] <= 1.010
    drop_pass= r['ath_drop'] >= 60
    cv_pass  = r['cv'] >= 0.001

    if not (ar_pass and drop_pass and cv_pass):
        return None  # 不满足条件

    # AR权重double：5分区间不变，改为max(0, 5-(ar-1)*800)
    ar_sc  = max(0, 5 - (r['ar'] - 1.000) * 800)   # 1.000→5分, 1.006→2分, 1.010→0分
    cv_sc  = max(0, 5 - r['cv'] * 400)              # 0.010→2.5分
    adx_sc = max(0, 5 - r['adx'] / 8 * 5)
    vol_sc = max(0, min(5, r['vol_ratio']))
    bt_sc  = 5 if r['breakout'] else 0
    # ATL反弹加成（跌幅>=60% 且 跌幅<90% 是黄金区间）
    atl_bonus = 3 if (60 <= r['ath_drop'] < 90) else (5 if r['ath_drop'] >= 90 else 0)
    return ar_sc + cv_sc + adx_sc + vol_sc + bt_sc + atl_bonus

# ─── 应用各方案 ─────────────────────────────────────────────────────────
print("=" * 85)
print(f"{'代码':<18} {'跌幅%':<8} {'AR':<8} {'CV':<8} {'ADX':<6} {'放量':<7} {'突破'}")
print("-" * 85)

# 展示所有满足跌幅>=50%的标的，用不同方案评分
candidates = [r for r in results if r['ath_drop'] >= 50 and r['cv'] >= 0.001]
candidates.sort(key=lambda x: x['ath_drop'], reverse=True)

scored_A = []
scored_B = []
scored_C = []

for r in candidates:
    vA = calc_score_vA(r)
    vB, drop_ok = calc_score_vB(r)
    vC = calc_score_vC(r)

    scored_A.append((r, vA))
    scored_B.append((r, vB, drop_ok))
    scored_C.append((r, vC))

# Top10 方案A
print("\n【方案A】当前权重（ATH跌幅参与评分，满分30）")
scored_A.sort(key=lambda x: x[1], reverse=True)
for i, (r, s) in enumerate(scored_A[:10], 1):
    bt = '🚀' if r['breakout'] else '   '
    print(f"{i:<4} {r['symbol']:<18} {r['ath_drop']:<8.1f} {r['ar']:<8.4f} {r['cv']:<8.4f} {r['adx']:<6.2f} {r['vol_ratio']:<6.2f}x {bt}  → {s:.1f}")

# Top10 方案B
print("\n【方案B】ATH跌幅改为>=50%硬过滤（满分25，AR权重不变）")
scored_B.sort(key=lambda x: x[1], reverse=True)
for i, (r, s, ok) in enumerate(scored_B[:10], 1):
    ok_mark = '✅' if ok else '❌'
    bt = '🚀' if r['breakout'] else '   '
    print(f"{i:<4} {r['symbol']:<18} {r['ath_drop']:<8.1f} {r['ar']:<8.4f} {r['cv']:<8.4f} {r['adx']:<6.2f} {r['vol_ratio']:<6.2f}x {bt}{ok_mark} → {s:.1f}")

# 方案C（只展示通过双重过滤的）
print("\n【方案C】AR<=1.010 + 跌幅>=60% 双重硬过滤 + AR权重×2 + 跌幅60-90%加3分")
scored_C_valid = [(r, s) for (r, s) in scored_C if s is not None]
scored_C_valid.sort(key=lambda x: x[1], reverse=True)
for i, (r, s) in enumerate(scored_C_valid, 1):
    bt = '🚀' if r['breakout'] else '   '
    print(f"{i:<4} {r['symbol']:<18} {r['ath_drop']:<8.1f} {r['ar']:<8.4f} {r['cv']:<8.4f} {r['adx']:<6.2f} {r['vol_ratio']:<6.2f}x {bt}  → {s:.1f}")

# ─── 关键对比：如果只看AR排名 ───────────────────────────────────────────
print("\n\n【仅看AR排名】所有AR<=1.010的标的（不看跌幅）")
ar_good = [r for r in results if r['ar'] <= 1.010 and r['cv'] >= 0.001]
ar_good.sort(key=lambda x: x['ar'])
for i, r in enumerate(ar_good[:20], 1):
    bt = '🚀' if r['breakout'] else ''
    print(f"{i:<4} {r['symbol']:<18} AR={r['ar']:<8.4f} CV={r['cv']:<8.4f} 跌幅={r['ath_drop']:<8.1f}%")

print(f"\n（共 {len(ar_good)} 个标的 AR <= 1.010）")

# ─── 交叉验证：AR好+跌幅够深 ──────────────────────────────────────────
print("\n\n【交集】AR<=1.008 且 跌幅>=50% — 最强横盘+够深底部")
cross = [r for r in results if r['ar'] <= 1.008 and r['ath_drop'] >= 50 and r['cv'] >= 0.001]
cross.sort(key=lambda x: x['ar'])
for i, r in enumerate(cross, 1):
    bt = '🚀' if r['breakout'] else ''
    print(f"{i:<4} {r['symbol']:<18} AR={r['ar']:<8.4f} CV={r['cv']:<8.4f} ADX={r['adx']:<6.2f} 跌幅={r['ath_drop']:<8.1f}% 放量={r['vol_ratio']:<6.2f}x {bt}")
