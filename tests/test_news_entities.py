from packages.quant.news.asset_mapping import map_entities_to_assets
from packages.quant.news.entities import extract_entities


def test_extracts_known_company_and_currency_entities():
    entities = extract_entities("Apple supplier warns about chip shortages amid Fed rate decision")
    types_values = {(e.type, e.value) for e in entities}
    assert ("COMPANY", "AAPL") in types_values
    assert ("CENTRAL_BANK", "FED") in types_values
    assert ("SECTOR", "SEMICONDUCTOR") in types_values


def test_no_hallucinated_entities_for_unrelated_headline():
    entities = extract_entities("Local bakery wins regional pastry competition")
    assert entities == []


def test_longer_alias_wins_over_substring_alias():
    entities = extract_entities("S&P 500 index rises on strong earnings")
    values = {e.value for e in entities}
    assert "SPX" in values


def test_direct_company_mapping():
    entities = extract_entities("Apple supplier warns about chip shortages amid Fed rate decision")
    universe = {"AAPL", "NVDA", "NDX", "SPX", "XAU", "BTCUSDT"}
    mappings = map_entities_to_assets(entities, universe)
    by_symbol = {m.asset_symbol: m for m in mappings}
    assert by_symbol["AAPL"].is_direct is True
    # Fed is an indirect driver for equity indices, not the stock itself.
    assert by_symbol["NDX"].is_direct is False


def test_asset_not_in_universe_is_never_mapped():
    entities = extract_entities("Tesla unveils new manufacturing facility")
    mappings = map_entities_to_assets(entities, {"AAPL"})  # TSLA deliberately excluded
    assert mappings == []


def test_direct_mapping_wins_over_indirect_for_same_symbol():
    entities = extract_entities("Nvidia leads semiconductor sector rally")
    universe = {"NVDA", "NDX"}
    mappings = map_entities_to_assets(entities, universe)
    by_symbol = {m.asset_symbol: m for m in mappings}
    # NVDA is named directly AND is an indirect "sector peer" driver --
    # direct must win, never silently downgraded.
    assert by_symbol["NVDA"].is_direct is True
