from dataclasses import dataclass


@dataclass
class CostModel:
    """成本模型"""

    fee_rate: float = 0.001  # 默认 0.1%
    slippage: float = 0.0005  # 默认 0.05%
    funding_rate: float = 0.0  # 仅合约

    @classmethod
    def spot_default(cls) -> "CostModel":
        return cls(fee_rate=0.002, slippage=0.0005)

    @classmethod
    def futures_default(cls) -> "CostModel":
        return cls(fee_rate=0.0005, slippage=0.0003)

    def total_cost_per_trade(self) -> float:
        return self.fee_rate + self.slippage
