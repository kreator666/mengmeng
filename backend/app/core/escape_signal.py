"""
逃顶信号合成规则（纯函数，不依赖数据获取）

规则（见 docs/逃顶信号策略方案.md）：
- 综合评分 = 价格层(0-100) + 新闻层加分(0-20) + 仪表盘层加分(0-30)，封顶 100
- 红（逃顶信号）：价格层判级C(评分≥60) ｜ 综合≥70 ｜ 仪表盘≥2项红灯且价格≥40
- 黄（警惕）：综合≥40 ｜ 价格层判级B
- 绿（正常）：其余
"""

LIGHT_GREEN = "green"
LIGHT_YELLOW = "yellow"
LIGHT_RED = "red"

RED_TOTAL_THRESHOLD = 70
YELLOW_TOTAL_THRESHOLD = 40
PRICE_C_THRESHOLD = 60
DASH_RED_PER_ITEM = 7.5


def dashboard_score(status_map: dict[str, str]) -> tuple[float, int, list[str]]:
    """
    仪表盘层加分：每项红灯 +7.5（封顶 30）
    返回 (加分, 红灯数, 理由)
    """
    red_items = [k for k, v in status_map.items() if v == "red"]
    score = min(len(red_items) * DASH_RED_PER_ITEM, 30.0)
    reasons = [f"仪表盘红灯 {len(red_items)} 项：{'、'.join(red_items)}"] if red_items else []
    return score, len(red_items), reasons


def composite_light(
    regime: str,
    price_score: float,
    news_score: float,
    dash_score: float,
    dash_red_count: int,
) -> tuple[str, float, list[str]]:
    """
    综合判级
    返回 (灯色 green/yellow/red, 综合评分, 判级理由)
    """
    total = min(price_score + news_score + dash_score, 100.0)
    reasons = []

    if price_score >= PRICE_C_THRESHOLD:
        return LIGHT_RED, total, [f"价格层情景C（评分{price_score:.0f}≥{PRICE_C_THRESHOLD}），硬触发逃顶信号"]
    if total >= RED_TOTAL_THRESHOLD:
        return LIGHT_RED, total, [f"综合评分{total:.0f}≥{RED_TOTAL_THRESHOLD}，触发逃顶信号"]
    if dash_red_count >= 2 and price_score >= YELLOW_TOTAL_THRESHOLD:
        return LIGHT_RED, total, [
            f"仪表盘{dash_red_count}项红灯且价格层评分{price_score:.0f}≥{YELLOW_TOTAL_THRESHOLD}，触发逃顶信号"
        ]

    if total >= YELLOW_TOTAL_THRESHOLD:
        reasons.append(f"综合评分{total:.0f}≥{YELLOW_TOTAL_THRESHOLD}")
        return LIGHT_YELLOW, total, reasons
    if regime == "B":
        return LIGHT_YELLOW, total, ["价格层情景B（高位消化）"]

    return LIGHT_GREEN, total, ["各层无极端信号"]


def light_changed(prev_light: str | None, new_light: str) -> bool:
    """推送去抖：仅灯色变化时需要推送"""
    return prev_light is not None and prev_light != new_light
