import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.data.sentinel_store import DASHBOARD_INDICATORS, SentinelStore


def _store():
    tmp = tempfile.TemporaryDirectory()
    return SentinelStore(Path(tmp.name) / "test.db"), tmp


def test_scan_daily_upsert():
    print("=" * 60)
    print("测试哨兵存储：scan_daily 幂等覆盖")
    print("=" * 60)

    store, tmp = _store()
    rec = {"date": "2026-07-18", "regime": "B", "price_score": 20, "news_score": 5,
           "dash_score": 0, "total_score": 25, "light": "yellow", "reasons": {"price": ["x"]}}
    store.upsert_scan(rec)
    store.upsert_scan({**rec, "total_score": 30})  # 当日重复扫描覆盖

    latest = store.latest_scan()
    assert latest["total_score"] == 30, f"当日应覆盖，实际 {latest['total_score']}"
    assert latest["reasons"]["price"] == ["x"]

    store.upsert_scan({**rec, "date": "2026-07-17", "total_score": 10})
    hist = store.scan_history(90)
    assert len(hist) == 2 and hist[0]["date"] == "2026-07-17", "历史应按日期升序"
    assert store.latest_scan()["date"] == "2026-07-18"
    print("   [OK] 幂等覆盖 + 历史排序\n")
    tmp.cleanup()


def test_news_hits_dedup():
    print("=" * 60)
    print("测试哨兵存储：news_hits 去重")
    print("=" * 60)

    store, tmp = _store()
    hit = {"id": "n1", "date": "2026-07-18", "title": "t", "url": "u", "source": "s",
           "tickers": ["NVDA"], "matched_keywords": ["capex cut"], "heavy": True,
           "published_at": "2026-07-18T10:00:00"}
    assert store.add_news_hits([hit]) == 1
    assert store.add_news_hits([hit]) == 0, "同 id 不应重复入库"

    news = store.recent_news(7)
    assert len(news) == 1 and news[0]["heavy"] is True
    assert news[0]["matched_keywords"] == ["capex cut"]
    print("   [OK] 文章 id 去重\n")
    tmp.cleanup()


def test_dashboard_crud():
    print("=" * 60)
    print("测试哨兵存储：dashboard 录入与最新灯态")
    print("=" * 60)

    store, tmp = _store()
    ind = DASHBOARD_INDICATORS[0]
    store.upsert_dashboard("2026Q2", ind, "red", "7250亿E", "增速放缓")
    store.upsert_dashboard("2026Q2", ind, "yellow")  # 同季同指标覆盖
    entries = store.list_dashboard("2026Q2")
    assert len(entries) == 1 and entries[0]["status"] == "yellow", "同季同指标应覆盖"

    status = store.latest_dashboard_status()
    assert status[ind] == "yellow"
    assert all(status[k] == "green" for k in DASHBOARD_INDICATORS if k != ind), "未录入指标默认绿"

    store.upsert_dashboard("2026Q3", DASHBOARD_INDICATORS[1], "red")
    status = store.latest_dashboard_status()
    assert status[DASHBOARD_INDICATORS[1]] == "red", "应取最新季度"
    assert status[ind] == "green", "旧季度录入不影响最新季度默认"
    print("   [OK] 录入覆盖 + 最新季度灯态\n")
    tmp.cleanup()


def test_signal_events():
    print("=" * 60)
    print("测试哨兵存储：signal_events 记录")
    print("=" * 60)

    store, tmp = _store()
    store.add_event("green", "yellow", 45.0, False, {"date": "2026-07-18"})
    store.add_event("yellow", "red", 72.0, True)
    events = store.list_events()
    assert len(events) == 2
    assert events[0]["to_light"] == "red" and events[0]["notified"] is True, "应按时间倒序"
    assert events[1]["detail"]["date"] == "2026-07-18"
    print("   [OK] 事件记录与倒序\n")
    tmp.cleanup()


if __name__ == "__main__":
    test_scan_daily_upsert()
    test_news_hits_dedup()
    test_dashboard_crud()
    test_signal_events()
    print("全部哨兵存储测试通过")
