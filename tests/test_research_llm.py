from packages.llm.client import LLMClient
from packages.llm.research import propose_rule

_STATS = {"sample_size": 30, "win_rate": 0.3, "expectancy": -0.4, "regime": "ranging"}


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
    assert propose_rule(_UnavailableLLMClient(), scope="pattern:breakout:ranging", stats=_STATS) is None


def test_accepts_well_formed_response():
    client = _FakeLLMClient({"condition": {"regime": "ranging"}, "conclusion": "Breakouts fail in ranging markets.", "confidence": 0.6})
    rule = propose_rule(client, scope="pattern:breakout:ranging", stats=_STATS)
    assert rule is not None
    assert rule.condition == {"regime": "ranging"}
    assert rule.conclusion == "Breakouts fail in ranging markets."
    assert rule.confidence == 0.6


def test_non_dict_response_is_discarded():
    client = _FakeLLMClient(["not", "a", "dict"])
    assert propose_rule(client, scope="pattern:breakout:ranging", stats=_STATS) is None


def test_missing_fields_are_discarded():
    client = _FakeLLMClient({"conclusion": "no condition or confidence"})
    assert propose_rule(client, scope="pattern:breakout:ranging", stats=_STATS) is None


def test_non_object_condition_is_discarded():
    client = _FakeLLMClient({"condition": "not an object", "conclusion": "x", "confidence": 0.5})
    assert propose_rule(client, scope="pattern:breakout:ranging", stats=_STATS) is None


def test_out_of_range_confidence_is_discarded():
    client = _FakeLLMClient({"condition": {}, "conclusion": "x", "confidence": 1.5})
    assert propose_rule(client, scope="pattern:breakout:ranging", stats=_STATS) is None


def test_empty_conclusion_is_discarded():
    client = _FakeLLMClient({"condition": {}, "conclusion": "  ", "confidence": 0.5})
    assert propose_rule(client, scope="pattern:breakout:ranging", stats=_STATS) is None
