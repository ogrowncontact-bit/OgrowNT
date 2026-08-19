from packages.data.connectors.macro.base import MacroCalendarProvider
from packages.data.connectors.macro.mock import MockMacroCalendarProvider
from packages.shared.settings import get_settings

_PROVIDERS = {
    "mock": MockMacroCalendarProvider,
    # TODO(real-macro-data): register real adapters here once implemented.
}


def get_macro_calendar_provider() -> MacroCalendarProvider:
    settings = get_settings()
    provider_cls = _PROVIDERS.get(settings.macro_calendar_provider)
    if provider_cls is None:
        raise ValueError(
            f"Unknown MACRO_CALENDAR_PROVIDER={settings.macro_calendar_provider!r}. "
            f"Available: {sorted(_PROVIDERS)}"
        )
    return provider_cls()
