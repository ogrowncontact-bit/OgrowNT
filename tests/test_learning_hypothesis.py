from packages.llm.client import LLMClient
from packages.llm.learning import generate_trade_hypothesis

_CONTEXT = dict(
    strategy_code="momentum_v1", asset_symbol="BTCUSDT", direction="long",
    regime="trending_bull", pattern_type="momentum", news_direction="aligned",
    outcome="loss", pnl=-10.0, r_multiple=-1.0, exit_reason="stop_hit",
)


class _FakeLLMClient(LLMClient):
    def __init__(self, response):
        self._response = response

    def is_available(self):
        return True

    def complete_json(self, system_prompt, user_content, max_tokens=1024):
        return self._response


class _UnavailableLLMClient(LLMClient):
    def __init__(self):
        pass

    def is_available(self):
        return False


def test_skips_when_llm_unavailable():
    assert generate_trade_hypothesis(_UnavailableLLMClient(), **_CONTEXT) is None


def test_accepts_well_formed_response():
    client = _FakeLLMClient({"hypothesis": "Regime shifted mid-trade.", "root_cause": "regime_shift"})
    result = generate_trade_hypothesis(client, **_CONTEXT)
    assert result is not None
    assert result.hypothesis == "Regime shifted mid-trade."
    assert result.root_cause == "regime_shift"


def test_non_dict_response_is_discarded():
    client = _FakeLLMClient(["not", "a", "dict"])
    assert generate_trade_hypothesis(client, **_CONTEXT) is None


def test_missing_fields_are_discarded():
    client = _FakeLLMClient({"hypothesis": "only half"})
    assert generate_trade_hypothesis(client, **_CONTEXT) is None


def test_empty_strings_are_discarded():
    client = _FakeLLMClient({"hypothesis": "   ", "root_cause": ""})
    assert generate_trade_hypothesis(client, **_CONTEXT) is None


def test_long_hypothesis_is_truncated():
    client = _FakeLLMClient({"hypothesis": "x" * 3000, "root_cause": "normal_variance"})
    result = generate_trade_hypothesis(client, **_CONTEXT)
    assert result is not None
    assert len(result.hypothesis) == 2000
