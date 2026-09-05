"""提交 strong24 候选因子池到天梯。"""
from __future__ import annotations
import asyncio
from submit_combo import submit

NAMES = [
    "GAP723", "PANIC_BUY",
    "KLEN", "KLOW", "LOW0",
    "MIN10", "MIN60",
    "QTLD30", "QTLD60",
    "ROC30", "ROC60",
    "STD5", "STD10",
    "CORR10", "CORD20",
    "VSUMN60", "VSUMP60", "VMA60",
    "SUMN30", "SUMP30",
    "MA30", "MA60",
    "IMIN60", "RSV60",
]

async def main():
    await submit(NAMES, note="strong24", benchmark="IF")

if __name__ == "__main__":
    asyncio.run(main())
