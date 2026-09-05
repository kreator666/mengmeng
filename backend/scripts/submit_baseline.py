"""提交 BETA60 基准组合。"""
from __future__ import annotations
import asyncio
from submit_combo import submit

NAMES = [
    "GAP723", "PANIC_BUY",
    "QTLD60", "LOW0", "ROC60", "VSUMP60", "CNTN30", "QTLU30",
    "MIN20", "MIN30",
    "CORR10", "KLEN",
    "MIN5", "MIN10", "MIN60",
    "VSUMN60", "MA60", "CORD20", "STD10",
    "IMIN60", "VMA60", "RSV60", "SUMN30", "BETA60",
]

async def main():
    await submit(NAMES, note="baseline_beta60_reload", benchmark="IF")

if __name__ == "__main__":
    asyncio.run(main())
