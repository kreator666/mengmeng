"""
算力链逃顶信号编排服务

流程：拉价格（Tiingo 日线）→ 价格层情景判级 → 拉新闻（Tiingo News）→ 新闻层评分
     → 读仪表盘录入 → 综合判级 → 落库 → 灯色变化时推送（由 notify 模块注入）

研究框架：research/OpenAI算力绑定_思维框架与投资指导.md
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Awaitable, Callable

# 复用 factor/ 目录的研究版哨兵因子
FACTOR_DIR = Path(__file__).resolve().parents[3] / "factor"
if str(FACTOR_DIR) not in sys.path:
    sys.path.insert(0, str(FACTOR_DIR))

from openai_chain_sentinel import (  # noqa: E402
    BENCHMARK,
    CHAIN_MEMBERS,
    calculate_chain_factors,
    calculate_chain_risk_factors,
    chain_regime,
    chain_risk_signal,
)

from app.core.escape_signal import (  # noqa: E402
    LIGHT_GREEN,
    composite_light,
    dashboard_score,
    light_changed,
)
from app.core.news_analyzer import load_keywords, match_article, news_layer_score  # noqa: E402
from app.core.notify import load_config  # noqa: E402
from app.data.news_client import TiingoNewsClient  # noqa: E402
from app.data.sentinel_store import SentinelStore  # noqa: E402
from app.data.sina_news_client import SinaNewsClient  # noqa: E402
from app.data.us_stock_client import USStockClient  # noqa: E402

# 推送器签名：async (from_light, to_light, total_score, detail) -> bool（是否成功）
Notifier = Callable[[str, str, float, dict], Awaitable[bool]]

PRICE_LOOKBACK_DAYS = 400
NEWS_LOOKBACK_DAYS = 7


async def fetch_chain_prices(client: USStockClient) -> dict[str, Any]:
    """拉取链成员 + QQQ 近 400 天日线（区间请求，避免耗尽免费配额）"""
    start = (datetime.utcnow() - timedelta(days=PRICE_LOOKBACK_DAYS)).strftime("%Y-%m-%d")
    end = datetime.utcnow().strftime("%Y-%m-%d")
    price_map = {}
    for sym in list(CHAIN_MEMBERS) + [BENCHMARK]:
        try:
            df = await client._fetch_range(sym, start, end)
            if df is not None and not df.empty:
                price_map[sym] = df
        except Exception:
            continue  # 单品种失败不阻断整体扫描
    return price_map


def price_layer(price_map: dict) -> dict[str, Any]:
    """价格层：篮子情景判级 + 成员风险评分"""
    chain = calculate_chain_factors(price_map)
    last = chain.index[-1]
    regime, score, reasons = chain_regime(chain, last)

    members = []
    for sym, role in CHAIN_MEMBERS.items():
        if sym not in price_map:
            continue
        f = calculate_chain_risk_factors(price_map[sym])
        _, s, rs = chain_risk_signal(f, f.index[-1])
        members.append({"symbol": sym, "role": role, "risk_score": s, "reasons": rs})

    return {
        "regime": regime,
        "score": score,
        "reasons": reasons,
        "members": members,
        "basket_ret": chain["basket_ret"],
        "as_of": last.date().isoformat(),
    }


async def run_scan(
    store: SentinelStore | None = None,
    notifier: Notifier | None = None,
    stock_client: USStockClient | None = None,
    news_client: TiingoNewsClient | None = None,
) -> dict[str, Any]:
    """
    执行一次完整扫描并存档（按价格最后交易日幂等，当日重复触发覆盖）
    返回完整扫描结果 dict
    """
    store = store or SentinelStore()
    own_stock = stock_client is None
    own_news = news_client is None
    stock_client = stock_client or USStockClient()
    if news_client is None:
        provider = load_config().get("news", {}).get("provider", "sina")
        news_client = TiingoNewsClient() if provider == "tiingo" else SinaNewsClient()

    try:
        # 1. 价格层
        price_map = await fetch_chain_prices(stock_client)
        if BENCHMARK not in price_map:
            raise Exception(f"价格数据获取失败：缺少基准 {BENCHMARK}")
        pl = price_layer(price_map)

        # 2. 新闻层
        keywords = load_keywords()
        hits = []
        try:
            articles = await news_client.fetch_news(
                list(CHAIN_MEMBERS), days=NEWS_LOOKBACK_DAYS, limit=1000)
            for art in articles:
                m = match_article(art, keywords, list(CHAIN_MEMBERS))
                if m:
                    hits.append({**art, **m})
        except Exception as e:
            hits_error = str(e)
        else:
            hits_error = None
        store.add_news_hits(hits)
        news_score, news_reasons = news_layer_score(hits, pl["basket_ret"])

        # 3. 仪表盘层
        dash_status = store.latest_dashboard_status()
        dash_score, dash_red_count, dash_reasons = dashboard_score(dash_status)

        # 4. 综合判级
        light, total, light_reasons = composite_light(
            pl["regime"], pl["score"], news_score, dash_score, dash_red_count
        )
        prev = store.latest_scan()
        prev_light = prev["light"] if prev else None

        record = {
            "date": pl["as_of"],
            "regime": pl["regime"],
            "price_score": pl["score"],
            "news_score": news_score,
            "dash_score": dash_score,
            "total_score": total,
            "light": light,
            "reasons": {
                "price": pl["reasons"],
                "news": news_reasons,
                "dashboard": dash_reasons,
                "light": light_reasons,
                "news_error": hits_error,
            },
        }
        store.upsert_scan(record)

        # 5. 灯色变化 → 信号事件 + 推送
        notified = False
        if light_changed(prev_light, light):
            detail = {"date": record["date"], "reasons": record["reasons"]}
            if notifier:
                try:
                    notified = await notifier(prev_light, light, total, detail)
                except Exception:
                    notified = False
            store.add_event(prev_light, light, total, notified, detail)

        return {
            **record,
            "prev_light": prev_light,
            "members": pl["members"],
            "news_hits": len(hits),
            "dashboard_status": dash_status,
            "notified": notified,
        }
    finally:
        if own_stock:
            await stock_client.close()
        if own_news:
            await news_client.close()
