# OpenAI 算力链风险哨兵因子 - 可复用代码
#
# 背景与研究框架：research/OpenAI算力绑定_思维框架与投资指导.md
# 思路：OpenAI 循环交易链上个股的单日暴跌/集体破位是整条链的传染起点
# （实证：2026-04-29 营收放缓报道→AI股集体跳水；2026-06-26 IPO推迟报道→软银-13%）
#
# 三种用法：
#   1) 单标的回测接口 factor(df)：把任一链上股票的 OHLCV 转成「链风险信号强度」
#      （正值=风险预警信号强度0-100，0=无信号；语义与做多因子相反，可用作减仓/过滤）
#   2) 组合哨兵接口 calculate_chain_factors(price_map) + chain_regime(...)：
#      用一篮子链上股票 + QQQ 基准，输出 情景A/B/C 判级（对应投资指导图三情景）
#   3) 命令行：python factor/openai_chain_sentinel.py
#      通过 backend 的 Tiingo 客户端拉取真实数据，打印当前链状态与情景判级

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# 循环交易链成员（Tiingo 代码）：角色越靠近 OpenAI 合同，同源风险越高
CHAIN_MEMBERS = {
    "NVDA": "芯片·英伟达",
    "AMD": "芯片·AMD(认股权证)",
    "AVGO": "芯片·博通",
    "ORCL": "云·甲骨文(3000亿合同)",
    "CRWV": "租赁·CoreWeave",
    "SFTBY": "资本·软银ADR",
    "MSFT": "云·微软",
    "AMZN": "云·亚马逊",
}
BENCHMARK = "QQQ"


# ---------------------------------------------------------------- 单标的链风险因子
def calculate_chain_risk_factors(df):
    """
    计算单只链上股票的链风险因子
    适用于：OpenAI 绑定链个股的破位/暴跌传染预警
    """
    factors = pd.DataFrame(index=df.index)

    # 1. 跌幅（链上个股单日暴跌是传染起点）
    factors['return_1'] = df['close'].pct_change(1) * 100
    factors['return_5'] = df['close'].pct_change(5) * 100

    # 2. 趋势破位
    factors['ma60'] = df['close'].rolling(60).mean()
    factors['ma120'] = df['close'].rolling(120).mean()
    factors['below_ma60'] = df['close'] < factors['ma60']
    factors['below_ma120'] = df['close'] < factors['ma120']

    # 3. 高点回撤（120 日）
    factors['high_120'] = df['close'].rolling(120).max()
    factors['drawdown_120'] = (df['close'] / factors['high_120'] - 1) * 100

    # 4. 放量下跌（恐慌出逃）
    factors['volume_ma10'] = df['volume'].rolling(10).mean()
    factors['volume_ratio'] = df['volume'] / factors['volume_ma10']
    factors['is_down'] = df['close'] < df['open']

    return factors


def chain_risk_signal(factors, idx):
    """
    判断链风险预警信号
    返回: (是否信号, 信号强度0-100, 理由)
    """
    score = 0
    reasons = []

    # 1. 单日暴跌
    r1 = factors.loc[idx, 'return_1']
    if r1 <= -7:
        score += 40
        reasons.append("单日暴跌%.1f%%" % r1)
    elif r1 <= -5:
        score += 25
        reasons.append("单日大跌%.1f%%" % r1)
    elif r1 <= -3:
        score += 10
        reasons.append("单日下跌%.1f%%" % r1)

    # 2. 五日跌幅
    r5 = factors.loc[idx, 'return_5']
    if r5 <= -15:
        score += 30
        reasons.append("5日重挫%.1f%%" % r5)
    elif r5 <= -10:
        score += 20
        reasons.append("5日大跌%.1f%%" % r5)
    elif r5 <= -5:
        score += 10
        reasons.append("5日下跌%.1f%%" % r5)

    # 3. 趋势破位
    if factors.loc[idx, 'below_ma120']:
        score += 15
        reasons.append("跌破MA120长期趋势")
    elif factors.loc[idx, 'below_ma60']:
        score += 10
        reasons.append("跌破MA60中期趋势")

    # 4. 高点深度回撤
    dd = factors.loc[idx, 'drawdown_120']
    if dd <= -30:
        score += 15
        reasons.append("120日高点回撤%.1f%%" % dd)
    elif dd <= -20:
        score += 10
        reasons.append("120日高点回撤%.1f%%" % dd)

    # 5. 放量下跌
    if factors.loc[idx, 'volume_ratio'] > 2 and factors.loc[idx, 'is_down']:
        score += 10
        reasons.append("放量下跌(量比%.2f)" % factors.loc[idx, 'volume_ratio'])

    is_signal = score >= 50
    return is_signal, min(score, 100), reasons


def factor(df):
    """
    系统回测接口：接收 OHLCV DataFrame，返回风险信号 Series
    正值 = 链风险预警信号强度（0-100），0 = 无信号
    注意：语义与做多因子相反，用作减仓/对冲/过滤信号
    """
    factors = calculate_chain_risk_factors(df)
    signal_values = np.zeros(len(df))

    for i in range(len(df)):
        idx = df.index[i]
        is_signal, score, _ = chain_risk_signal(factors, idx)
        if is_signal:
            signal_values[i] = score

    return pd.Series(signal_values, index=df.index)


# ------------------------------------------------------------------ 组合链哨兵
def calculate_chain_factors(price_map, members=None, benchmark=BENCHMARK):
    """
    计算算力链篮子的组合因子

    price_map: {symbol: OHLCV DataFrame}（需含 timestamp/close）
    返回按交易日对齐的因子 DataFrame；成员上市时间不同，按当日可用成员等权
    """
    members = members or list(CHAIN_MEMBERS)

    closes = {}
    for sym, df in price_map.items():
        if df is None or df.empty:
            continue
        s = df.set_index(pd.to_datetime(df['timestamp']).dt.normalize())['close']
        closes[sym] = s[~s.index.duplicated(keep='last')]

    if benchmark not in closes:
        raise ValueError("price_map 缺少基准 %s" % benchmark)
    avail = [m for m in members if m in closes]
    if len(avail) < 3:
        raise ValueError("可用链成员不足 3 个: %s" % avail)

    close_df = pd.DataFrame(closes).sort_index()
    ret = close_df.pct_change(1) * 100

    factors = pd.DataFrame(index=close_df.index)

    # 1. 等权链篮子（当日数据可用的成员，至少3个）
    member_ret = ret[avail]
    factors['n_members'] = member_ret.notna().sum(axis=1)
    basket_ret = member_ret.mean(axis=1).where(factors['n_members'] >= 3)
    factors['basket_ret'] = basket_ret
    factors['basket_index'] = (1 + basket_ret.fillna(0) / 100).cumprod() * 100
    factors['qqq_index'] = (1 + ret[benchmark].fillna(0) / 100).cumprod() * 100

    # 2. 动量与相对强度（链条是否还跑赢市场）
    factors['mom_20'] = factors['basket_index'].pct_change(20) * 100
    factors['mom_60'] = factors['basket_index'].pct_change(60) * 100
    qqq_ret_20 = factors['qqq_index'].pct_change(20) * 100
    factors['rs_20'] = factors['mom_20'] - qqq_ret_20

    # 3. 成员健康度：站上 MA60 的成员占比
    above = close_df[avail].gt(close_df[avail].rolling(60).mean())
    factors['frac_above_ma60'] = above.sum(axis=1) / close_df[avail].notna().sum(axis=1)

    # 4. 传染预警：近5日成员单日暴跌(≤-7%)次数
    crashes = (ret[avail] <= -7).astype(int)
    factors['crash_count_5d'] = crashes.rolling(5).sum().sum(axis=1)

    # 5. 篮子波动率（20日，年化%）
    factors['vol_20'] = basket_ret.rolling(20).std() * np.sqrt(252)

    return factors


def chain_regime(factors, idx):
    """
    链状态情景判级（对应投资指导图三情景）
    返回: (情景'A'/'B'/'C', 风险评分0-100, 理由)
    """
    score = 0
    reasons = []

    crashes = factors.loc[idx, 'crash_count_5d']
    mom20 = factors.loc[idx, 'mom_20']
    mom60 = factors.loc[idx, 'mom_60']
    rs20 = factors.loc[idx, 'rs_20']
    frac = factors.loc[idx, 'frac_above_ma60']

    # 情景C触发条件（循环破裂）：传染性暴跌 / 短期重挫 / 集体破位且跑输
    if crashes >= 3:
        score += 50
        reasons.append("近5日成员暴跌%d次(传染)" % crashes)
    elif crashes >= 1:
        score += 20
        reasons.append("近5日成员暴跌%d次" % crashes)

    if mom20 <= -15:
        score += 30
        reasons.append("篮子20日跌%.1f%%" % mom20)
    elif mom20 <= -8:
        score += 15
        reasons.append("篮子20日回调%.1f%%" % mom20)

    if frac < 0.3:
        score += 20
        reasons.append("仅%.0f%%成员站上MA60" % (frac * 100))
    elif frac < 0.5:
        score += 10
        reasons.append("%.0f%%成员站上MA60" % (frac * 100))

    if rs20 <= -10:
        score += 10
        reasons.append("跑输QQQ %.1f个百分点" % (-rs20))

    if score >= 60:
        return 'C', min(score, 100), reasons

    # 情景A（良性循环）：动量为正 + 跑赢基准 + 成员普遍健康 + 无传染
    if mom60 > 0 and rs20 > 0 and frac >= 0.6 and crashes == 0:
        return 'A', score, reasons or ["动量为正、跑赢基准、成员健康"]

    # 基准情形：高位估值消化
    return 'B', score, reasons or ["无极端信号，高位消化"]


# ------------------------------------------------------------------ 命令行：真实数据
def _fetch_chain_prices():
    """通过 backend 的 Tiingo 客户端拉取链成员 + QQQ 日线"""
    backend = Path(__file__).resolve().parents[1] / "backend"
    sys.path.insert(0, str(backend))

    import asyncio
    from datetime import datetime, timedelta
    from app.data.us_stock_client import USStockClient

    async def main():
        client = USStockClient()
        start = (datetime.utcnow() - timedelta(days=400)).strftime("%Y-%m-%d")
        end = datetime.utcnow().strftime("%Y-%m-%d")
        price_map = {}
        try:
            for sym in list(CHAIN_MEMBERS) + [BENCHMARK]:
                try:
                    # 哨兵只需近400天：走区间请求（每品种1次），
                    # 避免 fetch_klines 首次补全历史（约50次/品种）耗尽免费配额
                    df = await client._fetch_range(sym, start, end)
                    if df is not None and not df.empty:
                        price_map[sym] = df
                        print("  [数据] %-6s %d 根日线" % (sym, len(df)))
                    else:
                        print("  [跳过] %s 无数据" % sym)
                except Exception as e:
                    print("  [跳过] %s: %s" % (sym, e))
        finally:
            await client.close()
        return price_map

    return asyncio.run(main())


if __name__ == "__main__":
    print("=" * 60)
    print("OpenAI 算力链风险哨兵（Tiingo 真实数据）")
    print("=" * 60)

    prices = _fetch_chain_prices()
    chain = calculate_chain_factors(prices)
    last = chain.index[-1]

    regime, score, reasons = chain_regime(chain, last)
    print("\n日期: %s" % last.date())
    print("情景判级: %s（风险评分 %d/100）" % (
        {"A": "A 良性循环延续", "B": "B 高位估值消化", "C": "C 循环破裂预警"}[regime], score))
    for r in reasons:
        print("  -", r)

    print("\n链成员状态：")
    for sym, role in CHAIN_MEMBERS.items():
        if sym not in prices:
            continue
        f = calculate_chain_risk_factors(prices[sym])
        _, s, rs = chain_risk_signal(f, f.index[-1])
        print("  %-6s %-24s 风险评分 %3d  %s" % (sym, role, s, "；".join(rs) if rs else "正常"))
    print("  %-6s %-24s（基准）" % (BENCHMARK, "纳指ETF"))

# 使用示例
# 单标的：signal = factor(df)
# 组合：  chain = calculate_chain_factors(price_map); regime, score, reasons = chain_regime(chain, chain.index[-1])
