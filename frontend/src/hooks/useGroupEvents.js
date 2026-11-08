import { useEffect, useRef, useState } from "react";
import { api } from "../services/api";

/**
 * Subscribes to the group's Server-Sent Events stream so every open tab/phone
 * sees new expenses and settlements instantly. Calls onEvent(evt) for changes.
 */
export function useGroupEvents(groupId, onEvent) {
  const [status, setStatus] = useState("offline"); // offline | connecting | live
  const [listeners, setListeners] = useState(0);
  const handler = useRef(onEvent);
  handler.current = onEvent;

  useEffect(() => {
    if (!groupId || typeof EventSource === "undefined") return;
    setStatus("connecting");
    const es = new EventSource(api.eventsUrl(groupId));
    es.onopen = () => setStatus("live");
    es.onerror = () => setStatus("connecting"); // EventSource auto-reconnects
    es.onmessage = (msg) => {
      try {
        const evt = JSON.parse(msg.data);
        if (evt.type === "connected") setListeners(evt.listeners);
        else handler.current?.(evt);
      } catch {
        /* ignore malformed */
      }
    };
    return () => {
      es.close();
      setStatus("offline");
    };
  }, [groupId]);

  return { status, listeners };
}
