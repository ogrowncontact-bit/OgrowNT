from packages.data.connectors.news.base import NewsProvider
from packages.data.connectors.news.mock import MockNewsProvider
from packages.shared.settings import get_settings

_PROVIDERS = {
    "mock": MockNewsProvider,
    # TODO(real-news-data): register real adapters here once implemented.
}


def get_news_provider() -> NewsProvider:
    settings = get_settings()
    provider_cls = _PROVIDERS.get(settings.news_provider)
    if provider_cls is None:
        raise ValueError(f"Unknown NEWS_PROVIDER={settings.news_provider!r}. Available: {sorted(_PROVIDERS)}")
    return provider_cls()
