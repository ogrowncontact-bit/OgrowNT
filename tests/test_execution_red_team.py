"""Universal Broker & Exchange Connectivity red-team battery -- "PROMPT 13"
§99. 20 adversarial checks targeting this phase's central constraint:
"EXECUTION MUST BE BLOCKED" for anything but paper, and that no AI/agent/
strategy/research/LLM code path can reach a broker, a credential, or the
live-trading firewall's own internals directly. Each item either attempts a
concrete attack and confirms it fails safely, or structurally proves an
invariant an attacker (or a buggy AI-generated code path) would need to
break to succeed -- same technique as tests/test_capital_defense_red_team.py
("PROMPT 12" §132) and tests/test_research_red_team.py ("PROMPT 10" §57).
"""
from __future__ import annotations

import ast
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from packages.execution.broker.live import LiveBrokerAdapter
from packages.execution.broker.paper import PaperBrokerAdapter
from packages.execution.broker.registry import BrokerRegistry
from packages.execution.broker_reconciliation import run_broker_reconciliation_and_enforce
from packages.execution.firewall import ENABLE_LIVE_TRADING, LiveTradingDisabledError
from packages.execution.gate import evaluate
from packages.execution.instrument import get_instrument, validate_precision
from packages.execution.retry import RETRYABLE_OPERATIONS
from packages.execution.router import ExecutionRouter
from packages.execution.secrets import EnvSecretProvider, mask
from packages.shared.models import OHLCV, Asset, Signal, StrategyPerformance, StrategyRow, SystemState

REPO_ROOT = Path(__file__).resolve().parents[1]
AI_PACKAGES = (
    REPO_ROOT / "packages" / "agents",
    REPO_ROOT / "packages" / "research",
    REPO_ROOT / "packages" / "quant" / "strategies",
    REPO_ROOT / "apps" / "research_worker",
    REPO_ROOT / "packages" / "llm",
)
_NOW = datetime.now(timezone.utc)


def _iter_ai_source_files():
    for pkg in AI_PACKAGES:
        if not pkg.exists():
            continue
        for path in pkg.rglob("*.py"):
            if "__pycache__" in path.parts:
                continue
            yield path


def _asset_with_price(db_session, symbol: str, price: float, *, asset_class: str = "crypto") -> Asset:
    asset = Asset(symbol=symbol, asset_class=asset_class, is_active=True)
    db_session.add(asset)
    db_session.commit()
    db_session.add(OHLCV(asset_id=asset.id, timeframe="1m", ts=_NOW, open=price, high=price, low=price, close=price, volume=1000))
    db_session.commit()
    return asset


# 1. No AI/agent/research/strategy/LLM code imports the broker layer at all.
def test_1_no_ai_code_imports_the_broker_package():
    offenders = []
    for path in _iter_ai_source_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("packages.execution.broker"):
                offenders.append(f"{path.relative_to(REPO_ROOT)}: from {node.module} import ...")
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("packages.execution.broker"):
                        offenders.append(f"{path.relative_to(REPO_ROOT)}: import {alias.name}")
    assert offenders == [], f"AI-reachable broker import found: {offenders}"


# 2. No AI/agent/research/strategy/LLM code imports order_manager (the only code that creates Position/Trade rows).
def test_2_no_ai_code_imports_order_manager():
    offenders = []
    for path in _iter_ai_source_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "packages.execution.order_manager":
                offenders.append(f"{path.relative_to(REPO_ROOT)}")
    assert offenders == [], f"AI-reachable order_manager import found: {offenders}"


# 3. No AI/agent/research/strategy/LLM code imports the credential store.
def test_3_no_ai_code_imports_secrets():
    offenders = []
    for path in _iter_ai_source_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "packages.execution.secrets":
                offenders.append(f"{path.relative_to(REPO_ROOT)}")
    assert offenders == [], f"AI-reachable credential-store import found: {offenders}"


# 4. No AI/agent/research/strategy/LLM code assigns SystemState.trading_mode directly.
def test_4_no_ai_code_assigns_trading_mode_directly():
    offenders = []
    for path in _iter_ai_source_files():
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr == "trading_mode":
                        offenders.append(f"{path.relative_to(REPO_ROOT)}")
    assert offenders == [], f"AI-reachable trading_mode assignment found: {offenders}"


# 5. LiveTradingFirewall denies 'live' unconditionally, regardless of any other check outcome.
def test_5_firewall_denies_live_even_when_every_other_input_is_pristine(db_session):
    asset = _asset_with_price(db_session, "REDTEAMLIVE", 100.0)
    strategy = StrategyRow(code="redteam_live_strategy", name="x", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = Signal(strategy_id=strategy.id, asset_id=asset.id, direction="long", entry_price=100.0, stop_price=95.0, status="approved")
    db_session.add(signal)
    db_session.commit()

    live_state = SystemState(id=True, trading_mode="live", trading_enabled=True)  # never persisted -- DB CHECK forbids it
    approval = evaluate(
        db_session, signal_row=signal, asset=asset, direction="long", entry_price=100.0, stop_price=95.0,
        quantity=1.0, system_state=live_state, now=_NOW,
    )
    assert approval.approved is False
    assert "live_trading_blocked" in approval.reason


# 6. The database schema itself refuses 'live' as a legal trading_mode value -- layer 1 of defense-in-depth.
def test_6_database_check_constraint_refuses_live_trading_mode(db_session):
    db_session.add(SystemState(id=True, trading_mode="paper", trading_enabled=True))
    db_session.commit()
    with pytest.raises(IntegrityError):
        db_session.execute(text("UPDATE system_state SET trading_mode = 'live' WHERE id = true"))
        db_session.flush()
    db_session.rollback()


# 7. LiveBrokerAdapter self-destructs on instantiation -- layer 3, even if layers 1-2 were bypassed.
def test_7_live_broker_adapter_cannot_be_used_even_if_directly_instantiated():
    with pytest.raises(LiveTradingDisabledError):
        LiveBrokerAdapter()


# 8. ENABLE_LIVE_TRADING is hardcoded False, and no source file anywhere sets it True.
def test_8_enable_live_trading_constant_is_never_overridden_to_true_anywhere_in_the_repo():
    assert ENABLE_LIVE_TRADING is False
    needle = "ENABLE_LIVE_TRADING" + " = True"  # split so this very file's search string can't self-match
    offenders = []
    for path in REPO_ROOT.rglob("*.py"):
        if "__pycache__" in path.parts or ".venv" in path.parts or "node_modules" in path.parts:
            continue
        if path == Path(__file__):
            continue
        if needle in path.read_text():
            offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == [], f"ENABLE_LIVE_TRADING = True found outside firewall.py's own tripwire: {offenders}"


# 9. ExecutionRouter never selects a 'live'-kind adapter, even when explicitly registered as default.
def test_9_router_never_selects_a_live_kind_adapter_even_as_the_registered_default():
    class _LiveStub:
        name, kind = "sneaky_live", "live"
        def health_check(self):
            class _R:
                ok, latency_ms, detail = True, 0.1, {}
            return _R()
        def get_fees(self, **_):
            return 0.0
        def get_capabilities(self):
            from packages.execution.broker.capabilities import PAPER_CAPABILITIES
            return PAPER_CAPABILITIES

    registry = BrokerRegistry()
    registry.register(_LiveStub(), is_default=True)
    assert ExecutionRouter().select_broker(registry, asset_class="crypto", order_type="market") is None


# 10. Negative expectancy blocks the order even though risk/portfolio approval already happened upstream.
def test_10_negative_net_expectancy_vetoes_regardless_of_upstream_approval(db_session):
    asset = _asset_with_price(db_session, "REDTEAMEXPECT", 100.0)
    strategy = StrategyRow(code="redteam_expect_strategy", name="x", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = Signal(strategy_id=strategy.id, asset_id=asset.id, direction="long", entry_price=100.0, stop_price=95.0, status="approved")
    db_session.add(signal)
    db_session.add(StrategyPerformance(strategy_id=strategy.id, as_of=_NOW, window_trades=50, total_trades=50, expectancy=-50.0))
    db_session.commit()

    approval = evaluate(
        db_session, signal_row=signal, asset=asset, direction="long", entry_price=100.0, stop_price=95.0,
        quantity=1.0, system_state=SystemState(id=True, trading_mode="paper", trading_enabled=True), now=_NOW,
    )
    assert approval.approved is False


# 11. Credentials are never exposed by the masking helper, however short or long the underlying secret.
def test_11_credential_masking_never_returns_the_raw_value():
    assert mask("super-secret-api-key-value") != "super-secret-api-key-value"
    assert mask("ab") == "****"
    assert mask(None) == "not_configured"
    provider = EnvSecretProvider()
    assert provider.get("DEFINITELY_NOT_A_REAL_ENV_VAR_XYZ") is None


# 12. Negative quantity (a sign-flip attempt) is blocked exactly like zero.
def test_12_negative_quantity_is_blocked(db_session):
    asset = _asset_with_price(db_session, "REDTEAMNEGQTY", 100.0)
    strategy = StrategyRow(code="redteam_negqty_strategy", name="x", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = Signal(strategy_id=strategy.id, asset_id=asset.id, direction="long", entry_price=100.0, stop_price=95.0, status="approved")
    db_session.add(signal)
    db_session.commit()

    approval = evaluate(
        db_session, signal_row=signal, asset=asset, direction="long", entry_price=100.0, stop_price=95.0,
        quantity=-5.0, system_state=SystemState(id=True, trading_mode="paper", trading_enabled=True), now=_NOW,
    )
    assert approval.approved is False
    assert approval.reason == "invalid_position_size"


# 13. Instrument precision is enforced even when every other gate would pass.
def test_13_precision_violation_is_not_short_circuited_away_by_other_passing_checks(db_session):
    asset = _asset_with_price(db_session, "REDTEAMPRECISION", 100.0)
    asset.min_notional = 1_000_000.0  # an absurd minimum guarantees this is the only failing check
    db_session.add(asset)
    db_session.commit()
    strategy = StrategyRow(code="redteam_precision_strategy", name="x", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = Signal(strategy_id=strategy.id, asset_id=asset.id, direction="long", entry_price=100.0, stop_price=95.0, status="approved")
    db_session.add(signal)
    db_session.commit()

    approval = evaluate(
        db_session, signal_row=signal, asset=asset, direction="long", entry_price=100.0, stop_price=95.0,
        quantity=1.0, system_state=SystemState(id=True, trading_mode="paper", trading_enabled=True), now=_NOW,
    )
    assert approval.approved is False
    assert approval.reason.startswith("precision_violation")


# 14. A broker reconciliation mismatch pauses NEW trades but never touches the sovereign Kill Switch.
def test_14_reconciliation_mismatch_pauses_trading_without_tripping_the_kill_switch(db_session):
    class _MismatchedStub:
        name = "stub"
        def get_account(self):
            from packages.execution.broker.base import AccountInfo
            return AccountInfo(balance=1.0, available_balance=1.0, equity=99_999_999.0, margin=0.0, margin_used=0.0, margin_available=1.0, currency="USD", ts=_NOW)
        def get_positions(self):
            return []
        def get_open_orders(self):
            return []

    from packages.execution.broker.registry import get_or_create_broker_row
    broker_row = get_or_create_broker_row(db_session, name="stub", kind="paper")
    db_session.commit()
    result = run_broker_reconciliation_and_enforce(db_session, _MismatchedStub(), broker_id=broker_row.id)
    assert result.ok is False

    state = db_session.get(SystemState, True)
    assert state.trading_paused is True
    assert state.trading_enabled is True  # the Kill Switch is untouched -- an accounting stop, not a market-risk one


# 15. A non-marketable limit order is honestly rejected, never left as a fabricated resting order.
def test_15_non_marketable_limit_never_leaves_a_fake_pending_order(db_session):
    from packages.execution.adapters.base import OrderRequest

    asset = _asset_with_price(db_session, "REDTEAMLIMIT", 100.0)
    adapter = PaperBrokerAdapter(db_session)
    result = adapter.submit_order(OrderRequest(asset_id=asset.id, symbol=asset.symbol, side="buy", order_type="limit", qty=1.0, limit_price=1.0))
    assert result.status == "rejected"  # never 'new'/'submitted' left hanging


# 16. Every order-mutating BrokerAdapter operation is excluded from the safe-retry allowlist.
def test_16_no_order_mutating_operation_is_ever_retryable():
    mutating_ops = {"create_order", "submit_order", "cancel_order", "replace_order"}
    assert mutating_ops.isdisjoint(RETRYABLE_OPERATIONS)


# 17. An expired signal is blocked even with a healthy broker and a marketable price.
def test_17_expired_signal_cannot_be_resurrected_by_an_otherwise_perfect_setup(db_session):
    asset = _asset_with_price(db_session, "REDTEAMEXPIRY", 100.0)
    strategy = StrategyRow(code="redteam_expiry_strategy", name="x", family="test", version="1.0")
    db_session.add(strategy)
    db_session.commit()
    signal = Signal(strategy_id=strategy.id, asset_id=asset.id, direction="long", entry_price=100.0, stop_price=95.0, status="approved", expires_at=_NOW - timedelta(seconds=1))
    db_session.add(signal)
    db_session.commit()

    approval = evaluate(
        db_session, signal_row=signal, asset=asset, direction="long", entry_price=100.0, stop_price=95.0,
        quantity=1.0, system_state=SystemState(id=True, trading_mode="paper", trading_enabled=True), now=_NOW,
    )
    assert approval.approved is False
    assert approval.reason == "signal_expired"


# 18. A NULL precision limit is never treated as "anything goes" by silently fabricating a pass reason.
def test_18_missing_precision_data_is_honestly_untested_not_silently_approved():
    asset = Asset(symbol="REDTEAMNULLPRECISION", asset_class="crypto", is_active=True)
    spec = get_instrument(asset)
    assert spec.tick_size is None and spec.min_notional is None
    result = validate_precision(quantity=1.0, price=1.0, instrument=spec)
    assert result.ok is True
    assert result.violations == []  # honestly nothing to flag, not a fabricated "verified safe"


# 19. Duplicate broker events are never double-processed.
def test_19_duplicate_broker_events_never_process_twice(db_session):
    from packages.execution.broker.registry import get_or_create_broker_row
    from packages.execution.broker_events import record_event
    from packages.shared.models import BrokerEvent

    broker_row = get_or_create_broker_row(db_session, name="paper", kind="paper")
    db_session.commit()
    record_event(db_session, broker_id=broker_row.id, event_type="health_check", payload={"state": "healthy"})
    db_session.commit()
    record_event(db_session, broker_id=broker_row.id, event_type="health_check", payload={"state": "healthy"})
    db_session.commit()
    assert db_session.query(BrokerEvent).filter(BrokerEvent.broker_id == broker_row.id).count() == 1


# 20. No AI/agent/research/strategy/LLM code path can reach a broker's capability/fee/instrument lookups either --
#     even the "read-only" surface of BrokerAdapter stays off-limits to AI code, since a call into it would still
#     require the (forbidden) broker import proven in test_1 above; this asserts the reverse direction holds too --
#     nothing in packages/execution/broker ever imports FROM an AI package (no accidental coupling either way).
def test_20_the_broker_package_never_imports_from_an_ai_package():
    broker_pkg = REPO_ROOT / "packages" / "execution" / "broker"
    ai_module_prefixes = ("packages.agents", "packages.research", "packages.quant.strategies", "apps.research_worker", "packages.llm")
    offenders = []
    for path in broker_pkg.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith(ai_module_prefixes):
                offenders.append(f"{path.relative_to(REPO_ROOT)}: from {node.module} import ...")
    assert offenders == [], f"broker package importing from an AI package: {offenders}"
