import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class BacktestResultStore:
    """
    回测结果持久化存储（JSON 文件，按 ID 索引）
    """

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.storage_path = self.data_dir / "backtest_results.json"
        self._results: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self):
        if not self.storage_path.exists():
            return
        try:
            with self.storage_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                self._results = data
        except Exception:
            self._results = {}

    def _save(self):
        with self.storage_path.open("w", encoding="utf-8") as f:
            json.dump(self._results, f, ensure_ascii=False, indent=2)

    def list(self, limit: int = 100) -> list[dict[str, Any]]:
        """按创建时间倒序返回结果列表"""
        items = list(self._results.values())
        items.sort(
            key=lambda x: x.get("created_at", ""),
            reverse=True,
        )
        return items[:limit]

    def get(self, result_id: str) -> dict[str, Any] | None:
        return self._results.get(result_id)

    def save(self, result_id: str, result: dict[str, Any]):
        now = datetime.now(timezone.utc).isoformat()
        record = {
            "id": result_id,
            "created_at": result.get("created_at", now),
            "updated_at": now,
            **result,
        }
        if "created_at" not in record:
            record["created_at"] = now
        self._results[result_id] = record
        self._save()

    def delete(self, result_id: str) -> bool:
        if result_id not in self._results:
            return False
        del self._results[result_id]
        self._save()
        return True
