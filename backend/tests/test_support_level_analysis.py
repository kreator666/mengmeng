import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd

from app.core.support_level_analysis import analyze


def _support_at(rows, lookback=60):
    """按策略公式计算当前支撑位：取已有历史最后 lookback 根"""
    window = rows[-lookback:]
    range_high = max(r["high"] for r in window)
    range_low = min(r["low"] for r in window)
    return (range_high - range_low) / 3 + range_low


def _make_data(scenario: str):
    """
    构造支撑位分析测试数据

    第 0-69 根：稳步上涨，形成区间
    第 70-72 根：回调，第 72 根盘中回踩支撑位但收盘守住 -> 触发事件
    之后按 scenario 分支：
      bounce: 10 根反弹（涨幅 > 5%）-> bounced
      broke:  直接收盘跌破支撑 -> broke
    """
    dates = pd.date_range("2024-01-01", periods=90, freq="h")
    rows = []
    close = 100.0

    def add(i, open_p, high, low, close_p, volume=1000):
        rows.append({
            "timestamp": dates[i],
            "open": open_p,
            "high": high,
            "low": low,
            "close": close_p,
            "volume": volume,
        })

    for i in range(70):
        open_p = close
        close = close * 1.008
        add(i, open_p, max(open_p, close) * 1.002, min(open_p, close) * 0.998, close)

    for i in range(70, 72):
        open_p = close
        close = close * 0.97
        add(i, open_p, max(open_p, close) * 1.002, min(open_p, close) * 0.998, close)

    support = _support_at(rows)
    open_p = close
    add(72, open_p, open_p * 1.005, support * 0.998, support * 1.01, volume=2500)
    close = support * 1.01

    if scenario == "bounce":
        for i in range(73, 83):
            open_p = close
            close = close * 1.01
            add(i, open_p, max(open_p, close) * 1.002, min(open_p, close) * 0.998, close)
    else:  # broke
        for i in range(73, 83):
            open_p = close
            close = close * 0.97
            add(i, open_p, max(open_p, close) * 1.002, min(open_p, close) * 0.995, close)

    for i in range(83, 90):
        open_p = close
        close = close * 1.001
        add(i, open_p, max(open_p, close) * 1.002, min(open_p, close) * 0.998, close)

    return pd.DataFrame(rows)


def test_analyze_bounce_scenario():
    print("=" * 60)
    print("测试支撑位分析：回踩后反弹场景")
    print("=" * 60)

    df = _make_data("bounce")
    result = analyze(df)
    events = result["events"]
    stats = result["stats"]

    print(f"   事件数量: {len(events)}")
    for e in events:
        print(f"   事件: {e['timestamp']} 支撑={e['support']:.2f} "
              f"最大反弹={e['max_bounce_pct'] * 100:.2f}% 状态={e['status']}")
    print(f"   统计: 回踩={stats['total_touches']} 反弹={stats['bounced_count']} "
          f"成功率={stats['success_rate']}")

    assert len(events) == 1, "应只触发一次回踩事件"
    assert events[0]["status"] == "bounced", "回踩后涨幅超过 5% 应判定为 bounced"
    assert stats["total_touches"] == 1
    assert stats["bounced_count"] == 1
    assert stats["broke_count"] == 0
    assert stats["success_rate"] == 1.0
    assert stats["current_support"] is not None
    assert len(result["points"]) == len(df) - 59, "前 59 根 warmup 应被剔除"

    print("[OK] 反弹场景测试通过\n")


def test_analyze_broke_scenario():
    print("=" * 60)
    print("测试支撑位分析：回踩后破位场景")
    print("=" * 60)

    df = _make_data("broke")
    result = analyze(df)
    events = result["events"]
    stats = result["stats"]

    print(f"   事件数量: {len(events)}")
    for e in events:
        print(f"   事件: {e['timestamp']} 支撑={e['support']:.2f} "
              f"最大反弹={e['max_bounce_pct'] * 100:.2f}% 状态={e['status']}")
    print(f"   统计: 回踩={stats['total_touches']} 破位={stats['broke_count']} "
          f"成功率={stats['success_rate']}")

    assert len(events) == 1, "应只触发一次回踩事件"
    assert events[0]["status"] == "broke", "回踩后收盘跌破支撑应判定为 broke"
    assert stats["bounced_count"] == 0
    assert stats["broke_count"] == 1
    assert stats["success_rate"] == 0.0

    print("[OK] 破位场景测试通过\n")


def test_analyze_pending_scenario():
    print("=" * 60)
    print("测试支撑位分析：数据末尾事件待定场景")
    print("=" * 60)

    # 只取到回踩确认 K 线为止，后续无任何 K 线 -> pending
    df = _make_data("bounce").iloc[:73]
    result = analyze(df)
    events = result["events"]

    print(f"   事件数量: {len(events)}, 状态: {[e['status'] for e in events]}")

    assert len(events) == 1
    assert events[0]["status"] == "pending", "回踩后没有后续 K 线应判定为 pending"

    print("[OK] 待定场景测试通过\n")


if __name__ == "__main__":
    test_analyze_bounce_scenario()
    test_analyze_broke_scenario()
    test_analyze_pending_scenario()
    print("全部支撑位分析测试通过")
