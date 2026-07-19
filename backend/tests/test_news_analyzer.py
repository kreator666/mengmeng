import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from app.core.news_analyzer import load_keywords, match_article, news_layer_score

KEYWORDS = load_keywords()
CHAIN = ["NVDA", "ORCL", "AMD", "AVGO", "CRWV", "SFTBY", "MSFT", "AMZN"]


def _article(title, description="", tickers=None, days_ago=1, news_id="1"):
    ts = (pd.Timestamp.utcnow() - pd.Timedelta(days=days_ago)).isoformat()
    return {
        "id": news_id, "title": title, "description": description,
        "url": "http://x", "source": "test", "published_at": ts,
        "tickers": tickers or [],
    }


def test_match_article():
    print("=" * 60)
    print("测试新闻分析器：文章匹配")
    print("=" * 60)

    # 链成员 ticker + 负面词 → 命中
    m = match_article(_article("NVDA supplier cuts guidance amid slowdown", tickers=["NVDA"]), KEYWORDS, CHAIN)
    assert m and "cuts guidance" in m["matched_keywords"] and not m["heavy"]
    print("   [OK] ticker + 负面词命中")

    # 无 ticker，但含 watch 词 openai + 重磅词 → 命中且 heavy
    m = match_article(_article("OpenAI postpones IPO to next year", tickers=[]), KEYWORDS, CHAIN)
    assert m and m["heavy"], f"应命中重磅词: {m}"
    print("   [OK] watch 词 + 重磅词命中，heavy=True")

    # 链相关但无负面词 → 不命中
    m = match_article(_article("NVDA launches new chip", tickers=["NVDA"]), KEYWORDS, CHAIN)
    assert m is None
    print("   [OK] 无负面词不命中")

    # 无关文章 → 不命中
    m = match_article(_article("Cocoa prices rally on shortage", tickers=["XXX"]), KEYWORDS, CHAIN)
    assert m is None
    print("   [OK] 无关文章不命中\n")


def test_news_layer_score_tiers():
    print("=" * 60)
    print("测试新闻分析器：评分分档")
    print("=" * 60)

    neg = lambda i, d: {**_article(f"OpenAI capex cut worries {i}", tickers=["NVDA"], days_ago=d, news_id=str(i)),
                        "matched_keywords": ["capex cut"], "heavy": False}

    # 0 条 → 0 分
    s, _ = news_layer_score([], None)
    assert s == 0, f"0 条应 0 分，实际 {s}"

    # 2 条 → 5 分
    s, _ = news_layer_score([neg(1, 1), neg(2, 2)], None)
    assert s == 5, f"2 条应 5 分，实际 {s}"

    # 3 条 → 10 分
    s, _ = news_layer_score([neg(i, i) for i in range(1, 4)], None)
    assert s == 10, f"3 条应 10 分，实际 {s}"

    # 5 条 → 15 分
    s, _ = news_layer_score([neg(i, i) for i in range(1, 6)], None)
    assert s == 15, f"5 条应 15 分，实际 {s}"
    print("   [OK] 0/2/3/5 条 → 0/5/10/15 分")

    # 重磅词额外 +5
    heavy_hit = {**_article("OpenAI delays IPO", tickers=["MSFT"], days_ago=1, news_id="h"),
                 "matched_keywords": ["delays ipo"], "heavy": True}
    s, reasons = news_layer_score([neg(1, 1), heavy_hit], None)
    assert s == 10, f"2条+重磅应 10 分，实际 {s}"
    print("   [OK] 重磅词额外 +5")

    # 8 天前的新闻不计入窗口
    s, _ = news_layer_score([neg(1, 8)], None)
    assert s == 0, f"超出 7 日窗口应 0 分，实际 {s}"
    print("   [OK] 7 日窗口过滤")

    # 市场验证 +5：命中当日篮子跌 ≥3%
    ret = pd.Series(
        [0.5, -3.5],
        index=[pd.Timestamp.utcnow().normalize() - pd.Timedelta(days=1),
               pd.Timestamp.utcnow().normalize()],
    )
    s, reasons = news_layer_score([neg(1, 0)], ret)
    assert s == 10, f"1条+市场验证应 10 分，实际 {s}"
    print("   [OK] 市场验证 +5")

    # 封顶 20
    many = [neg(i, 1) for i in range(10)] + [heavy_hit]
    s, _ = news_layer_score(many, ret)
    assert s == 20, f"应封顶 20，实际 {s}"
    print("   [OK] 封顶 20\n")


if __name__ == "__main__":
    test_match_article()
    test_news_layer_score_tiers()
    print("全部新闻分析器测试通过")
