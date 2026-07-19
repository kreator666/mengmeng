"""
算力链逃顶信号：独立扫描脚本（定时任务的兜底）

用法：
  backend/venv/Scripts/python.exe backend/scripts/run_sentinel_scan.py

可挂 Windows 计划任务，作为 FastAPI 进程内 APScheduler 之外的兜底；
灯色变化时按 backend/data/sentinel_config.json 配置推送。
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.chain_sentinel_service import run_scan
from app.core.notify import make_notifier


async def main():
    result = await run_scan(notifier=make_notifier())
    label = {"green": "绿·正常", "yellow": "黄·警惕", "red": "红·逃顶信号"}[result["light"]]
    print(f"[{result['date']}] 灯色: {label}  综合评分: {result['total_score']:.0f}/100  "
          f"情景: {result['regime']}  新闻命中: {result['news_hits']}  已推送: {result['notified']}")
    for r in result["reasons"]["light"]:
        print("  -", r)


if __name__ == "__main__":
    asyncio.run(main())
