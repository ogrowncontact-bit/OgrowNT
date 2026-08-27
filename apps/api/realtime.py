"""WebSocket gateway + DB-tail startup/shutdown hooks — "PROMPT 14" §70,
§107, §130-132.

The WebSocket endpoint is the ONLY thing here that's transport-specific;
everything it depends on (CentralEventBus, the tail loop's actual DB
reads/incident detection) lives in packages/events/ and is reusable/testable
without a socket. apps/api/main.py's lifespan calls start_realtime()/
stop_realtime() once per process.

Auth: a native browser WebSocket can't set an Authorization header, so the
same JWT the REST API already issues is passed as `?token=`. The dashboard
never stores it separately — apps/dashboard/app/api/ws-ticket/route.ts reads
the existing httpOnly `ogrownt_token` cookie server-side (the browser itself
can never read an httpOnly cookie) and hands the same token back to the
client JS once, over the same-origin HTTPS/HTTP connection the rest of the
dashboard already trusts.
"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, FastAPI, WebSocket, WebSocketDisconnect

from apps.api.security import decode_access_token
from packages.events.bus import CentralEventBus, Event
from packages.events.channels import CHANNELS
from packages.events.tailer import build_heartbeat_event, detect_incidents, tail_new_events
from packages.shared.db import SessionLocal
from packages.shared.models import AdminUser, Alert, TradingEvent
from packages.shared.settings import get_settings

logger = logging.getLogger("api.realtime")

router = APIRouter(tags=["realtime"])


def _authenticate(token: str | None) -> str | None:
    """Returns the admin's email, or None if the token is missing/invalid —
    never raises, since the caller (the WS endpoint) needs to close the
    socket with a clean code either way, not propagate an exception."""
    if not token:
        return None
    try:
        email = decode_access_token(token)
    except ValueError:
        return None
    db = SessionLocal()
    try:
        admin = db.query(AdminUser).filter(AdminUser.email == email).first()
        return admin.email if admin is not None else None
    finally:
        db.close()


@router.websocket("/ws/{channel}")
async def websocket_channel(websocket: WebSocket, channel: str) -> None:
    if channel not in CHANNELS:
        await websocket.close(code=4404)
        return

    token = websocket.query_params.get("token")
    email = _authenticate(token)
    if email is None:
        await websocket.close(code=4401)
        return

    bus: CentralEventBus = websocket.app.state.bus
    await websocket.accept()
    queue = bus.subscribe(channel)
    try:
        while True:
            event = await queue.get()
            await websocket.send_json(event.to_dict())
    except WebSocketDisconnect:
        pass
    finally:
        bus.unsubscribe(channel, queue)


async def _tail_loop(app: FastAPI) -> None:
    settings = get_settings()
    bus: CentralEventBus = app.state.bus

    db = SessionLocal()
    try:
        last_trading_event_id = db.query(TradingEvent.id).order_by(TradingEvent.id.desc()).limit(1).scalar() or 0
        last_alert_id = db.query(Alert.id).order_by(Alert.id.desc()).limit(1).scalar() or 0
    finally:
        db.close()

    while True:
        await asyncio.sleep(settings.event_poll_interval_seconds)
        db = SessionLocal()
        try:
            result = await asyncio.to_thread(
                tail_new_events, db, since_trading_event_id=last_trading_event_id, since_alert_id=last_alert_id,
            )
            last_trading_event_id = result.last_trading_event_id
            last_alert_id = result.last_alert_id
            for event in result.events:
                bus.publish(event)

            if result.events:
                incidents = await asyncio.to_thread(detect_incidents, db, result.events)
                for incident in incidents:
                    bus.publish(
                        Event(
                            event_type="incident_created", source="tailer", channel="alerts",
                            payload={"incident_id": incident.id, "category": incident.category, "title": incident.title},
                            severity=incident.severity,
                        )
                    )

            heartbeat = await asyncio.to_thread(build_heartbeat_event, db)
            bus.publish(heartbeat)
        except Exception:  # noqa: BLE001 - one bad tick must never kill the loop
            logger.exception("event tail loop iteration failed")
        finally:
            db.close()


def start_realtime(app: FastAPI) -> None:
    app.state.bus = CentralEventBus()
    app.state.tail_task = asyncio.create_task(_tail_loop(app))


async def stop_realtime(app: FastAPI) -> None:
    task = getattr(app.state, "tail_task", None)
    if task is not None:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
