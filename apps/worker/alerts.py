"""Alert delivery cycle — docs/blueprint/12-roadmap.md Phase 7's "canais de
alerta adicionais". Runs on its own cadence (settings.alert_delivery_interval_seconds,
apps/worker/main.py) rather than inline where each Alert is created, so every
alert-writing call site (packages/quant/learning/*, packages/risk/monitor.py,
apps/api/routers/system.py) stays simple — write the row, delivery is this
module's job alone.

Every not-yet-delivered Alert gets exactly one delivery attempt: `delivered_at`
is set the moment delivery is attempted, regardless of whether any channel
actually succeeded (packages/shared/models.py's Alert docstring explains why —
"not configured" is a valid completed state, and the alert is never lost
either way since it's still in the `alerts` table / dashboard). Per-channel
outcomes are recorded in `alert.meta["_delivery"]` for audit.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from packages.notifications.dispatcher import NotificationDispatcher
from packages.shared.models import Alert

logger = logging.getLogger("worker.alerts")


def run_alert_delivery_cycle(db: Session, dispatcher: NotificationDispatcher) -> dict:
    pending = db.query(Alert).filter(Alert.delivered_at.is_(None)).order_by(Alert.ts.asc()).all()
    attempted, sent = 0, 0

    for alert in pending:
        result = dispatcher.dispatch(alert)
        attempted += 1
        if result.any_sent:
            sent += 1

        alert.delivered_at = datetime.now(timezone.utc)
        alert.meta = {**alert.meta, "_delivery": [{"channel": r.channel, "status": r.status, "detail": r.detail} for r in result.results]}
        db.add(alert)

        if result.configured_channel_count == 0:
            logger.debug("Alert %s: no channels configured, marking attempted", alert.id)
        elif not result.any_sent:
            logger.warning("Alert %s: delivery attempted but no channel succeeded", alert.id)

    db.commit()
    summary = {"attempted": attempted, "sent": sent}
    if attempted:
        logger.info("Alert delivery cycle complete: %s", summary)
    return summary
