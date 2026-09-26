import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

/** WebSocket is an invalidation hint; REST remains the source of truth. */
export function useContestEvents(id: string | undefined) {
  const query = useQueryClient();
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    if (!id) return;
    let stopped = false;
    let socket: WebSocket | null = null;
    let retry: ReturnType<typeof setTimeout> | undefined;
    let delay = 1000;
    let previous = "";
    const connect = () => {
      if (stopped) return;
      socket = new WebSocket(
        `${location.protocol === "https:" ? "wss:" : "ws:"}//${location.host}/ws/contests/${encodeURIComponent(id)}`,
      );
      socket.onopen = () => {
        setConnected(true);
        delay = 1000;
        query.invalidateQueries({ queryKey: ["contest", id] });
      };
      socket.onmessage = (event) => {
        try {
          const { server_time: _, ...payload } = JSON.parse(event.data);
          const signature = JSON.stringify(payload);
          if (signature === previous) return;
          previous = signature;
          query.invalidateQueries({
            predicate: (q) => {
              const key = String(q.queryKey[0]);
              return (
                [
                  "contest",
                  "standings",
                  "monitor",
                  "submission",
                  "dashboard",
                ].includes(key) ||
                key.startsWith("/submissions") ||
                key.startsWith(`/contests/${id}/`) ||
                key === "/contests"
              );
            },
          });
        } catch {
          /* Malformed notifications never overwrite REST state. */
        }
      };
      socket.onerror = () => socket?.close();
      socket.onclose = () => {
        setConnected(false);
        if (stopped) return;
        retry = setTimeout(connect, delay);
        delay = Math.min(delay * 2, 30000);
      };
    };
    connect();
    return () => {
      stopped = true;
      if (retry) clearTimeout(retry);
      socket?.close();
    };
  }, [id, query]);
  return connected;
}
