"""Universal Broker & Exchange Connectivity — "PROMPT 13".

packages.execution.broker.base.BrokerAdapter is a superset Protocol built
on top of the existing packages.execution.adapters.base.ExecutionProvider
(unchanged, still used directly by anything that only needs submit_order/
cancel_order/get_order/get_balance). PaperBrokerAdapter is the only adapter
this codebase ever instantiates — see that module's own docstring and
docs/broker-execution-infrastructure.md.
"""
