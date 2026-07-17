from app.data.base_client import MarketDataClient
from app.data.binance_client import BinanceClient
from app.data.gateio_client import GateIOClient
from app.models.enums import Provider


_CLIENTS: dict[Provider, type[MarketDataClient]] = {
    Provider.GATEIO: GateIOClient,
    Provider.BINANCE: BinanceClient,
}


def get_client(provider: Provider) -> MarketDataClient:
    """根据 provider 获取对应行情客户端"""
    client_cls = _CLIENTS.get(provider)
    if not client_cls:
        raise ValueError(f"不支持的行情源: {provider}")
    return client_cls()
