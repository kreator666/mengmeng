"""
链风险哨兵存储（SQLite）

四张表（见 docs/逃顶信号策略方案.md）：
- scan_daily        每日扫描结果（date 主键，当日重复扫描覆盖）
- news_hits         命中负面关键词的新闻（文章 id 去重）
- dashboard_entries 仪表盘四指标季度录入
- signal_events     灯色变化与推送记录
"""

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

DB_FILE = Path(__file__).resolve().parents[2] / "data" / "sentinel.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS scan_daily (
    date TEXT PRIMARY KEY,
    regime TEXT,
    price_score REAL,
    news_score REAL,
    dash_score REAL,
    total_score REAL,
    light TEXT,
    reasons_json TEXT,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS news_hits (
    news_id TEXT PRIMARY KEY,
    date TEXT,
    title TEXT,
    url TEXT,
    source TEXT,
    tickers TEXT,
    matched_keywords TEXT,
    heavy INTEGER,
    published_at TEXT
);
CREATE TABLE IF NOT EXISTS dashboard_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    quarter TEXT,
    indicator TEXT,
    status TEXT,
    value_text TEXT,
    note TEXT,
    updated_at TEXT,
    UNIQUE(quarter, indicator)
);
CREATE TABLE IF NOT EXISTS signal_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT,
    from_light TEXT,
    to_light TEXT,
    total_score REAL,
    notified INTEGER,
    detail_json TEXT
);
"""

# 仪表盘四项指标（固定顺序，前端按此渲染）
DASHBOARD_INDICATORS = [
    "capex_growth",        # 巨头 capex 环比增速
    "openai_next_round",   # OpenAI 下轮融资倍数
    "first_slowdown",      # 首个宣布减速的巨头
    "backlog_concentration",  # backlog 欠款方集中度
]


class SentinelStore:
    def __init__(self, db_path: Path | str | None = None):
        self.db_path = Path(db_path) if db_path else DB_FILE
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    @contextmanager
    def _conn(self):
        """事务执行并确保连接关闭（with sqlite3.Connection 只管提交，不管关闭）"""
        conn = self._connect()
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def _init(self):
        with self._conn() as conn:
            conn.executescript(_SCHEMA)

    # ---------------------------------------------------------- scan_daily
    def upsert_scan(self, record: dict[str, Any]):
        """按日期覆盖写入当日扫描结果（幂等）"""
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO scan_daily
                   (date, regime, price_score, news_score, dash_score,
                    total_score, light, reasons_json, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    record["date"], record["regime"], record["price_score"],
                    record["news_score"], record["dash_score"], record["total_score"],
                    record["light"], json.dumps(record.get("reasons", {}), ensure_ascii=False),
                    datetime.utcnow().isoformat(),
                ),
            )

    def latest_scan(self) -> dict[str, Any] | None:
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM scan_daily ORDER BY date DESC LIMIT 1"
            ).fetchone()
        return self._scan_row(row) if row else None

    def scan_history(self, days: int = 90) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM scan_daily ORDER BY date DESC LIMIT ?", (days,)
            ).fetchall()
        return [self._scan_row(r) for r in reversed(rows)]

    @staticmethod
    def _scan_row(row: sqlite3.Row) -> dict[str, Any]:
        d = dict(row)
        d["reasons"] = json.loads(d.pop("reasons_json") or "{}")
        return d

    # ---------------------------------------------------------- news_hits
    def add_news_hits(self, hits: list[dict[str, Any]]) -> int:
        """按文章 id 去重写入，返回新增条数"""
        inserted = 0
        with self._conn() as conn:
            for h in hits:
                cur = conn.execute(
                    """INSERT OR IGNORE INTO news_hits
                       (news_id, date, title, url, source, tickers,
                        matched_keywords, heavy, published_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        h["id"], h.get("date", ""), h.get("title", ""), h.get("url", ""),
                        h.get("source", ""), json.dumps(h.get("tickers", []), ensure_ascii=False),
                        json.dumps(h.get("matched_keywords", []), ensure_ascii=False),
                        1 if h.get("heavy") else 0, h.get("published_at", ""),
                    ),
                )
                inserted += cur.rowcount
        return inserted

    def recent_news(self, days: int = 7) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM news_hits ORDER BY published_at DESC LIMIT 200"
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["tickers"] = json.loads(d["tickers"] or "[]")
            d["matched_keywords"] = json.loads(d["matched_keywords"] or "[]")
            d["heavy"] = bool(d["heavy"])
            out.append(d)
        return out

    # ------------------------------------------------------ dashboard
    def upsert_dashboard(self, quarter: str, indicator: str, status: str,
                         value_text: str = "", note: str = ""):
        assert indicator in DASHBOARD_INDICATORS, f"未知指标: {indicator}"
        assert status in ("red", "yellow", "green"), f"未知状态: {status}"
        with self._conn() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO dashboard_entries
                   (id, quarter, indicator, status, value_text, note, updated_at)
                   VALUES (
                       (SELECT id FROM dashboard_entries WHERE quarter=? AND indicator=?),
                       ?, ?, ?, ?, ?, ?)""",
                (quarter, indicator, quarter, indicator, status,
                 value_text, note, datetime.utcnow().isoformat()),
            )

    def list_dashboard(self, quarter: str | None = None) -> list[dict[str, Any]]:
        with self._conn() as conn:
            if quarter:
                rows = conn.execute(
                    "SELECT * FROM dashboard_entries WHERE quarter=? ORDER BY id",
                    (quarter,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM dashboard_entries ORDER BY quarter DESC, id"
                ).fetchall()
        return [dict(r) for r in rows]

    def latest_dashboard_status(self) -> dict[str, str]:
        """最新季度各指标灯态：{indicator: status}，缺失视为 green"""
        rows = self.list_dashboard()
        latest_quarter = rows[0]["quarter"] if rows else None
        status = {ind: "green" for ind in DASHBOARD_INDICATORS}
        if latest_quarter:
            for r in rows:
                if r["quarter"] == latest_quarter:
                    status[r["indicator"]] = r["status"]
        return status

    # ------------------------------------------------------ signal_events
    def add_event(self, from_light: str | None, to_light: str,
                  total_score: float, notified: bool,
                  detail: dict[str, Any] | None = None):
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO signal_events (ts, from_light, to_light, total_score, notified, detail_json)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (datetime.utcnow().isoformat(), from_light, to_light, total_score,
                 1 if notified else 0, json.dumps(detail or {}, ensure_ascii=False)),
            )

    def list_events(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM signal_events ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        out = []
        for r in rows:
            d = dict(r)
            d["notified"] = bool(d["notified"])
            d["detail"] = json.loads(d.pop("detail_json") or "{}")
            out.append(d)
        return out
