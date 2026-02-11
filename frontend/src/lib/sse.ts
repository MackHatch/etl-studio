import { baseURL } from "./api";

export type SSERunPayload = {
  id: string;
  dataset_id: string;
  status: string;
  progress_percent: number;
  total_rows: number | null;
  processed_rows: number;
  success_rows: number;
  error_rows: number;
  started_at: string | null;
  finished_at: string | null;
  error_summary: string | null;
  created_at: string;
  updated_at: string;
};

export type SSEEvent = {
  event: string;
  data: SSERunPayload | { time?: string; code?: string; message?: string };
};

export type SSEConnectionStatus =
  | "connecting"
  | "open"
  | "reconnecting"
  | "closed";

const BACKOFF_BASE_MS = 1000;
const BACKOFF_MAX_MS = 15000;
const BACKOFF_MULTIPLIER = 2;

/**
 * Parse a single SSE message block (one or more "event:" and "data:" lines).
 * Supports multi-line data (multiple "data:" lines are joined with \n).
 */
function parseSSEMessage(block: string): { event: string; data: string } | null {
  let event = "message";
  const dataLines: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith("event:")) {
      event = line.slice(6).trim();
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).replace(/^\s/, ""));
    }
  }
  if (dataLines.length === 0) return null;
  return { event, data: dataLines.join("\n") };
}

export type ConnectRunEventsParams = {
  runId: string;
  token: string;
  onEvent: (ev: SSEEvent) => void;
  onStatus: (status: SSEConnectionStatus) => void;
};

export type ConnectRunEventsResult = {
  close: () => void;
};

/**
 * Connect to run SSE stream with automatic reconnect and backoff.
 * Reports status: connecting | open | reconnecting | closed.
 * Call close() to stop reconnecting.
 */
export function connectRunEvents({
  runId,
  token,
  onEvent,
  onStatus,
}: ConnectRunEventsParams): ConnectRunEventsResult {
  const url = `${baseURL}/api/runs/${runId}/events`;
  let aborted = false;
  let backoffMs = BACKOFF_BASE_MS;
  let isFirstConnect = true;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let currentAc: AbortController | null = null;

  function scheduleReconnect() {
    if (aborted) return;
    const delay = Math.min(backoffMs, BACKOFF_MAX_MS);
    backoffMs = Math.min(backoffMs * BACKOFF_MULTIPLIER, BACKOFF_MAX_MS);
    onStatus("reconnecting");
    reconnectTimer = setTimeout(() => runStream(), delay);
  }

  async function runStream() {
    if (aborted) {
      onStatus("closed");
      return;
    }
    currentAc = new AbortController();
    onStatus(isFirstConnect ? "connecting" : "reconnecting");
    isFirstConnect = false;

    try {
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
        signal: currentAc.signal,
      });
      if (!res.ok || !res.body) {
        scheduleReconnect();
        return;
      }
      onStatus("open");
      backoffMs = BACKOFF_BASE_MS;

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let terminalReceived = false;

      while (true) {
        if (aborted) break;
        const { done, value } = await reader.read().catch((e) => {
          if ((e as { name?: string }).name === "AbortError") return { done: true, value: undefined };
          throw e;
        });
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          if (!part.trim()) continue;
          const parsed = parseSSEMessage(part);
          if (!parsed) continue;
          try {
            const data = JSON.parse(parsed.data) as SSEEvent["data"];
            onEvent({ event: parsed.event, data });
            if (parsed.event === "run.completed" || parsed.event === "run.error") {
              terminalReceived = true;
              onStatus("closed");
              return;
            }
          } catch {
            onEvent({ event: parsed.event, data: { message: parsed.data } });
          }
        }
      }

      if (!aborted && !terminalReceived) scheduleReconnect();
    } catch (e) {
      if ((e as { name?: string }).name === "AbortError" || aborted) {
        onStatus("closed");
        return;
      }
      scheduleReconnect();
    }
  }

  runStream();

  return {
    close() {
      aborted = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      currentAc?.abort();
      onStatus("closed");
    },
  };
}

export type AdminRunsSSEPayload = {
  items?: Array<{
    id: string;
    dataset_id: string;
    dataset_name: string;
    status: string;
    progress_percent: number;
    processed_rows: number;
    total_rows: number | null;
    attempt_count: number;
    dlq: boolean;
    updated_at: string;
    last_error: string | null;
  }>;
  time?: string;
  message?: string;
};

export type ConnectAdminRunsEventsParams = {
  token: string;
  onEvent: (ev: { event: string; data: AdminRunsSSEPayload }) => void;
  onStatus: (status: SSEConnectionStatus) => void;
};

export type ConnectAdminRunsEventsResult = {
  close: () => void;
};

/**
 * Connect to admin runs SSE stream with automatic reconnect and backoff.
 * Emits runs.snapshot (initial), runs.changed (updates), runs.heartbeat.
 */
export function connectAdminRunsEvents({
  token,
  onEvent,
  onStatus,
}: ConnectAdminRunsEventsParams): ConnectAdminRunsEventsResult {
  const url = `${baseURL}/api/admin/runs/events`;
  let aborted = false;
  let backoffMs = BACKOFF_BASE_MS;
  let isFirstConnect = true;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let currentAc: AbortController | null = null;

  function scheduleReconnect() {
    if (aborted) return;
    const delay = Math.min(backoffMs, BACKOFF_MAX_MS);
    backoffMs = Math.min(backoffMs * BACKOFF_MULTIPLIER, BACKOFF_MAX_MS);
    onStatus("reconnecting");
    reconnectTimer = setTimeout(() => runStream(), delay);
  }

  async function runStream() {
    if (aborted) {
      onStatus("closed");
      return;
    }
    currentAc = new AbortController();
    onStatus(isFirstConnect ? "connecting" : "reconnecting");
    isFirstConnect = false;

    try {
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
        signal: currentAc.signal,
      });
      if (!res.ok || !res.body) {
        scheduleReconnect();
        return;
      }
      onStatus("open");
      backoffMs = BACKOFF_BASE_MS;

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        if (aborted) break;
        const { done, value } = await reader.read().catch((e) => {
          if ((e as { name?: string }).name === "AbortError") return { done: true, value: undefined };
          throw e;
        });
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";

        for (const part of parts) {
          if (!part.trim()) continue;
          const parsed = parseSSEMessage(part);
          if (!parsed) continue;
          try {
            const data = JSON.parse(parsed.data) as AdminRunsSSEPayload;
            onEvent({ event: parsed.event, data });
          } catch {
            onEvent({ event: parsed.event, data: { message: parsed.data } });
          }
        }
      }

      if (!aborted) scheduleReconnect();
    } catch (e) {
      if ((e as { name?: string }).name === "AbortError" || aborted) {
        onStatus("closed");
        return;
      }
      scheduleReconnect();
    }
  }

  runStream();

  return {
    close() {
      aborted = true;
      if (reconnectTimer) {
        clearTimeout(reconnectTimer);
        reconnectTimer = null;
      }
      currentAc?.abort();
      onStatus("closed");
    },
  };
}

/**
 * Legacy one-shot open (no reconnect). Prefer connectRunEvents for run detail.
 */
export function openRunEvents(
  runId: string,
  token: string,
  onEvent: (ev: SSEEvent) => void,
  onError?: (err: Error) => void
): () => void {
  const url = `${baseURL}/api/runs/${runId}/events`;
  const ac = new AbortController();

  (async () => {
    try {
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
        signal: ac.signal,
      });
      if (!res.ok || !res.body) {
        onError?.(new Error(res.statusText || "SSE request failed"));
        return;
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const part of parts) {
          if (!part.trim()) continue;
          const parsed = parseSSEMessage(part);
          if (!parsed) continue;
          try {
            const data = JSON.parse(parsed.data) as SSEEvent["data"];
            onEvent({ event: parsed.event, data });
          } catch {
            onEvent({ event: parsed.event, data: { message: parsed.data } });
          }
        }
      }
    } catch (e) {
      if ((e as { name?: string }).name !== "AbortError") {
        onError?.(e instanceof Error ? e : new Error(String(e)));
      }
    }
  })();

  return () => ac.abort();
}
