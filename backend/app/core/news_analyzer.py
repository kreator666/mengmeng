"""
链相关新闻分析器：关键词匹配 + 新闻层风险评分（0-20）

规则（见 docs/逃顶信号策略方案.md）：
- 近 7 日命中负面关键词的新闻：1-2 条 +5；3-4 条 +10；≥5 条 +15
- 命中重磅关键词（IPO推迟/融资失败级）额外 +5
- 市场验证：命中新闻当日链篮子跌幅 ≥3% 再 +5
- 总分封顶 20

词表在 backend/data/sentinel_keywords.json，改词不用改代码。
"""

import json
from pathlib import Path
from typing import Any

import pandas as pd

KEYWORDS_FILE = Path(__file__).resolve().parents[2] / "data" / "sentinel_keywords.json"


def load_keywords(path: Path | None = None) -> dict[str, list[str]]:
    """加载关键词词表（小写匹配）"""
    file = path or KEYWORDS_FILE
    with open(file, encoding="utf-8") as f:
        cfg = json.load(f)
    return {
        "heavy": [k.lower() for k in cfg.get("heavy_keywords", [])],
        "negative": [k.lower() for k in cfg.get("negative_keywords", [])],
        "watch": [k.lower() for k in cfg.get("watch_keywords", [])],
    }


def match_article(
    article: dict[str, Any],
    keywords: dict[str, list[str]],
    chain_tickers: list[str],
) -> dict[str, Any] | None:
    """
    判断文章是否链相关且命中负面/重磅关键词

    链相关：文章 tickers 含任一链成员，或标题/描述含 watch 词（openai/anthropic）
    返回 None 表示不相关或未命中；否则返回 {matched_keywords, heavy}
    """
    text = (article.get("title", "") + " " + article.get("description", "")).lower()
    article_tickers = {t.upper() for t in article.get("tickers", [])}

    relevant = bool(article_tickers & {t.upper() for t in chain_tickers})
    if not relevant:
        relevant = any(w in text for w in keywords["watch"])
    if not relevant:
        return None

    matched = [k for k in keywords["negative"] if k in text]
    heavy_hits = [k for k in keywords["heavy"] if k in text]
    matched += heavy_hits

    if not matched:
        return None
    return {"matched_keywords": matched, "heavy": bool(heavy_hits)}


def news_layer_score(
    hits: list[dict[str, Any]],
    basket_ret: pd.Series | None = None,
    window_days: int = 7,
    now: pd.Timestamp | None = None,
) -> tuple[int, list[str]]:
    """
    新闻层风险评分（0-20）

    hits: 命中记录列表，每条含 published_at / matched_keywords / heavy
    basket_ret: 链篮子日收益率序列（index 为日期），用于市场验证加分
    返回 (得分, 理由列表)
    """
    now = now or pd.Timestamp.utcnow()
    if now.tzinfo is not None:
        now = now.tz_convert("UTC").tz_localize(None)
    cutoff = now - pd.Timedelta(days=window_days)

    recent = []
    for h in hits:
        ts = pd.Timestamp(h["published_at"])
        if ts.tzinfo is not None:
            ts = ts.tz_convert("UTC").tz_localize(None)
        if ts >= cutoff:
            recent.append({**h, "_ts": ts})

    score = 0
    reasons = []

    n = len(recent)
    if n >= 5:
        score += 15
        reasons.append(f"近{window_days}日命中负面新闻{n}条")
    elif n >= 3:
        score += 10
        reasons.append(f"近{window_days}日命中负面新闻{n}条")
    elif n >= 1:
        score += 5
        reasons.append(f"近{window_days}日命中负面新闻{n}条")

    if any(h["heavy"] for h in recent):
        score += 5
        heavy_titles = [h.get("title", "") for h in recent if h["heavy"]][:2]
        reasons.append("命中重磅事件：" + "；".join(heavy_titles))

    # 市场验证：命中新闻当日链篮子跌 ≥3%
    if basket_ret is not None and not basket_ret.empty and recent:
        ret = basket_ret.copy()
        idx = pd.to_datetime(ret.index)
        if idx.tz is not None:
            idx = idx.tz_convert("UTC").tz_localize(None)
        ret.index = idx.normalize()
        validated = False
        for h in recent:
            day_ret = ret.get(h["_ts"].normalize())
            if day_ret is not None and not pd.isna(day_ret) and day_ret <= -3:
                validated = True
                break
        if validated:
            score += 5
            reasons.append("市场验证：命中新闻当日链篮子跌超3%")

    return min(score, 20), reasons
