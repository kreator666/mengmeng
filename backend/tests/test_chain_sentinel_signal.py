import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.escape_signal import (
    LIGHT_GREEN, LIGHT_RED, LIGHT_YELLOW,
    composite_light, dashboard_score, light_changed,
)


def test_dashboard_score():
    print("=" * 60)
    print("测试逃顶信号：仪表盘层加分")
    print("=" * 60)

    s, n, _ = dashboard_score({})
    assert s == 0 and n == 0

    s, n, _ = dashboard_score({"a": "red", "b": "green", "c": "yellow"})
    assert s == 7.5 and n == 1, f"1 红灯应 7.5 分，实际 {s}"

    s, n, _ = dashboard_score({"a": "red", "b": "red", "c": "red", "d": "red", "e": "red"})
    assert s == 30 and n == 5, f"应封顶 30，实际 {s}"
    print("   [OK] 0/1/5 红灯 → 0/7.5/30 分\n")


def test_composite_red_paths():
    print("=" * 60)
    print("测试逃顶信号：三条红色触发路径")
    print("=" * 60)

    # 路径1：价格层 C（评分≥60）硬触发
    light, total, _ = composite_light("C", 60, 0, 0, 0)
    assert light == LIGHT_RED and total == 60

    # 路径2：综合评分 ≥70
    light, total, _ = composite_light("B", 40, 20, 15, 0)
    assert light == LIGHT_RED and total == 75, f"实际 {light}/{total}"

    # 路径3：仪表盘 ≥2 红灯 且 价格层 ≥40
    light, _, _ = composite_light("B", 40, 0, 15, 2)
    assert light == LIGHT_RED

    # 反例：2 红灯但价格层 <40 → 不是红
    light, _, _ = composite_light("B", 30, 0, 15, 2)
    assert light != LIGHT_RED, f"价格层不足 40 不应触发红，实际 {light}"
    print("   [OK] 三条路径 + 反例\n")


def test_composite_yellow_green():
    print("=" * 60)
    print("测试逃顶信号：黄/绿边界")
    print("=" * 60)

    # 综合 ≥40 → 黄
    light, _, _ = composite_light("A", 30, 10, 0, 0)
    assert light == LIGHT_YELLOW

    # 判级 B → 黄
    light, _, _ = composite_light("B", 20, 0, 0, 0)
    assert light == LIGHT_YELLOW

    # 全平静 → 绿
    light, total, _ = composite_light("A", 0, 0, 0, 0)
    assert light == LIGHT_GREEN and total == 0

    # 综合封顶 100
    _, total, _ = composite_light("C", 100, 20, 30, 4)
    assert total == 100
    print("   [OK] 黄/绿边界 + 封顶 100\n")


def test_light_changed():
    print("=" * 60)
    print("测试逃顶信号：推送去抖")
    print("=" * 60)

    assert light_changed("green", "yellow") is True
    assert light_changed("yellow", "red") is True
    assert light_changed("red", "green") is True
    assert light_changed("red", "red") is False
    assert light_changed(None, "red") is False  # 首次扫描不推送
    print("   [OK] 仅灯色变化时推送，首次扫描不推\n")


if __name__ == "__main__":
    test_dashboard_score()
    test_composite_red_paths()
    test_composite_yellow_green()
    test_light_changed()
    print("全部逃顶信号合成规则测试通过")
