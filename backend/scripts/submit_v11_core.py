"""提交 11 因子精简组合 v11_core 到天梯。"""
from __future__ import annotations
import asyncio
from submit_combo import submit

NAMES = [
    "GAP723", "PANIC_BUY",
    "ROC60", "MA60", "CORR10", "VMA60", "VSUMN60", "VSUMP60",
    "LOW0", "STD10", "BETA60",
]

async def main():
    await submit(NAMES, note="v11_core", benchmark="IF")

if __name__ == "__main__":
    asyncio.run(main())
