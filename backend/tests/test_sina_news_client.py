import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.news_analyzer import load_keywords, match_article
from app.data.sina_news_client import detect_tickers, parse_feed


def _payload(items):
    return {"result": {"data": {"feed": {"list": items}}}}


def _item(rich_text, news_id=1, create_time="2026-07-19 09:30:00"):
    return {"id": news_id, "rich_text": rich_text, "docurl": "http://x",
            "create_time": create_time}


def test_parse_feed():
    print("=" * 60)
    print("测试新浪快讯：响应解析")
    print("=" * 60)

    payload = _payload([
        _item("【市场消息】英伟达与OpenAI洽谈新一轮算力合作<b>详情</b>", 101),
        _item("甲骨文公布财报，资本开支引关注", 102),
        _item("", 103),  # 空文本应被跳过
    ])
    arts = parse_feed(payload)

    assert len(arts) == 2, f"空文本应跳过，实际 {len(arts)} 条"
    a = arts[0]
    assert a["id"] == "101"
    assert "<b>" not in a["description"], "HTML 标签应被清除"
    assert set(a["tickers"]) == {"NVDA"}, f"ticker 识别错误: {a['tickers']}"
    assert a["published_at"].endswith("+08:00")
    assert arts[1]["tickers"] == ["ORCL"]
    assert a["source"] == "新浪财经7x24"
    print(f"   [OK] 解析/标签清除/ticker识别（示例标题: {a['title'][:20]}…）\n")


def test_detect_tickers():
    print("=" * 60)
    print("测试新浪快讯：ticker 别名识别")
    print("=" * 60)

    assert detect_tickers("软银集团宣布投资") == ["SFTBY"]
    assert set(detect_tickers("微软和亚马逊云业务竞争")) == {"MSFT", "AMZN"}
    assert detect_tickers("CoreWeave 上市首日大涨") == ["CRWV"]
    assert detect_tickers("国足战平对手") == []
    print("   [OK] 中/英别名 + 误命中防护\n")


def test_chinese_keyword_matching():
    print("=" * 60)
    print("测试新浪快讯：中文关键词接入分析器")
    print("=" * 60)

    keywords = load_keywords()
    chain = ["NVDA", "ORCL", "AMD", "AVGO", "CRWV", "SFTBY", "MSFT", "AMZN"]

    art = parse_feed(_payload([_item("报道称OpenAI推迟IPO计划，市场担忧其融资前景")]))[0]
    m = match_article(art, keywords, chain)
    assert m is not None and m["heavy"], f"推迟IPO应命中重磅词: {m}"
    print("   [OK] 「OpenAI推迟IPO」→ 重磅命中")

    art2 = parse_feed(_payload([_item("英伟达营收放缓引发担忧")]))[0]
    m2 = match_article(art2, keywords, chain)
    assert m2 is not None and "营收放缓" in m2["matched_keywords"] and not m2["heavy"]
    print("   [OK] 「英伟达营收放缓」→ 负面命中")

    art3 = parse_feed(_payload([_item("英伟达发布新一代芯片，性能翻倍")]))[0]
    assert match_article(art3, keywords, chain) is None
    print("   [OK] 正面新闻不误报\n")


if __name__ == "__main__":
    test_parse_feed()
    test_detect_tickers()
    test_chinese_keyword_matching()
    print("全部新浪快讯客户端测试通过")
