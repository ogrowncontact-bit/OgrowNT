"use client";

import { useEffect, useRef, useState } from "react";
import { getWsBaseUrl } from "./api";

// "PROMPT 14" §70, §102-103: the client-facing half of the real-time
// contract. A genuine, persistent WebSocket connection per channel, with
// exponential-backoff reconnect and honest staleness detection — this hook
// never lets a stalled/disconnected socket keep showing old data as if it
// were live (§102's "nunca fingir real-time"); `stale`/`status` exist
// specifically so a consuming component can render a visible warning
// instead.

export type StreamEvent = {
  event_id: string;
  event_type: string;
  source: string;
  channel: string;
  timestamp: string;
  payload: Record<string, unknown>;
  severity: "info" | "warning" | "critical";
  correlation_id: string | null;
};

export type StreamStatus = "connecting" | "open" | "closed" | "error";

// Comfortably above the server's own EVENT_POLL_INTERVAL_SECONDS default
// (2s, packages/shared/settings.py) plus reconnect slack — a channel with
// genuinely no traffic for a while (e.g. "news") shouldn't falsely read
// stale just because nothing happened, but a truly dead connection should
// be flagged well before a minute goes by.
const STALE_AFTER_MS = 20_000;
const MAX_BUFFER = 50;
const MAX_BACKOFF_MS = 15_000;

export function useEventStream(channel: string) {
  const [status, setStatus] = useState<StreamStatus>("connecting");
  const [events, setEvents] = useState<StreamEvent[]>([]);
  const [lastMessageAt, setLastMessageAt] = useState<number | null>(null);
  const [stale, setStale] = useState(false);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;
    let retry = 0;
    let reconnectTimer: ReturnType<typeof setTimeout> | undefined;

    async function connect() {
      if (cancelled) return;
      setStatus("connecting");

      let token: string;
      try {
        const res = await fetch("/api/ws-ticket", { cache: "no-store" });
        if (!res.ok) throw new Error("no ticket");
        const body = (await res.json()) as { token: string };
        token = body.token;
      } catch {
        if (!cancelled) {
          setStatus("error");
          scheduleReconnect();
        }
        return;
      }
      if (cancelled) return;

      const ws = new WebSocket(`${getWsBaseUrl()}/ws/${channel}?token=${encodeURIComponent(token)}`);
      wsRef.current = ws;

      ws.onopen = () => {
        if (cancelled) return;
        retry = 0;
        setStatus("open");
      };
      ws.onmessage = (msg) => {
        if (cancelled) return;
        try {
          const event = JSON.parse(msg.data as string) as StreamEvent;
          setEvents((prev) => [event, ...prev].slice(0, MAX_BUFFER));
          setLastMessageAt(Date.now());
          setStale(false);
        } catch {
          // A malformed frame is dropped, never crashes the UI over one bad message.
        }
      };
      ws.onclose = () => {
        if (cancelled) return;
        setStatus("closed");
        scheduleReconnect();
      };
      ws.onerror = () => {
        if (cancelled) return;
        setStatus("error");
      };
    }

    function scheduleReconnect() {
      if (cancelled) return;
      const delay = Math.min(1000 * 2 ** retry, MAX_BACKOFF_MS);
      retry += 1;
      reconnectTimer = setTimeout(connect, delay);
    }

    connect();

    return () => {
      cancelled = true;
      if (reconnectTimer) clearTimeout(reconnectTimer);
      wsRef.current?.close();
    };
  }, [channel]);

  useEffect(() => {
    const id = setInterval(() => {
      if (lastMessageAt !== null && Date.now() - lastMessageAt > STALE_AFTER_MS) {
        setStale(true);
      }
    }, 2000);
    return () => clearInterval(id);
  }, [lastMessageAt]);

  return { status, events, lastEvent: events[0] ?? null, stale };
}
