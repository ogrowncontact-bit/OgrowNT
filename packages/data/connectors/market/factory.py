from packages.data.connectors.market.base import MarketDataProvider
from packages.data.connectors.market.mock import MockMarketDataProvider
from packages.shared.settings import get_settings

_PROVIDERS = {
    "mock": MockMarketDataProvider,
    # TODO(real-market-data): register real adapters here once implemented,
    # e.g. "binance": BinanceProvider, "alpaca": AlpacaProvider.
}


def get_market_data_provider() -> MarketDataProvider:
    settings = get_settings()
    provider_cls = _PROVIDERS.get(settings.market_data_provider)
    if provider_cls is None:
        raise ValueError(
            f"Unknown MARKET_DATA_PROVIDER={settings.market_data_provider!r}. "
            f"Available: {sorted(_PROVIDERS)}"
        )
    return provider_cls()
