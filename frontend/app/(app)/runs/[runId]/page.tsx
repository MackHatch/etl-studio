"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { connectRunEvents, type SSERunPayload, type SSEConnectionStatus } from "@/lib/sse";
import { Button } from "@/components/ui/Button";
import { RunEventLog, type EventLogEntry } from "@/components/runs/RunEventLog";
import { RunErrorsPreview, type RowError } from "@/components/runs/RunErrorsPreview";
import { useRerun } from "@/features/schema/queries";

const MAX_EVENT_LOG = 50;

type RunDetail = {
  id: string;
  dataset_id: string;
  status: string;
  progress_percent: number;
  total_rows: number | null;
  processed_rows: number;
  success_rows: number;
  error_rows: number;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  error_summary: string | null;
  attempt_count: number;
  dlq: boolean;
  last_error: string | null;
  errors: RowError[];
};

type RunAttempt = {
  id: string;
  run_id: string;
  attempt_number: number;
  status: string;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
  traceback: string | null;
  created_at: string;
};

function isTerminal(status: string) {
  return status === "SUCCEEDED" || status === "FAILED";
}

function RerunSection({
  runId,
  onRerun,
}: {
  runId: string;
  onRerun: (newRunId: string) => void;
}) {
  const rerunMutation = useRerun(runId);
  const [error, setError] = useState<string | null>(null);

  async function handleRerun() {
    setError(null);
    try {
      const newRun = await rerunMutation.mutateAsync({});
      onRerun(newRun.id);
    } catch (e: any) {
      setError(e?.message || "Failed to rerun");
    }
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-medium text-gray-700">Rerun with active schema</h2>
      <p className="mt-1 text-sm text-gray-500">
        Create a new run from the same file using the current active schema version.
      </p>
      <Button
        data-testid="rerun-button"
        className="mt-3"
        onClick={handleRerun}
        disabled={rerunMutation.isPending}
      >
        {rerunMutation.isPending ? "Creating rerun…" : "Rerun with active schema"}
      </Button>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}

function StartRunSection({
  runId,
  datasetId,
  hasMapping,
  token,
  onStarted,
}: {
  runId: string;
  datasetId: string;
  hasMapping: boolean;
  token: string | null;
  onStarted: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function handleStart() {
    if (!token) return;
    setError(null);
    setLoading(true);
    try {
      await apiFetch(`/api/runs/${runId}/start`, { method: "POST" }, token);
      onStarted();
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to start");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-medium text-gray-700">Start import</h2>
      <p className="mt-1 text-sm text-gray-500">
        {hasMapping
          ? "Mapping is configured. Start the import to process the CSV."
          : "Configure column mapping first, then start the import."}
      </p>
      <Button
        data-testid="run-start"
        className="mt-3"
        onClick={handleStart}
        disabled={!hasMapping || loading}
      >
        {loading ? "Starting…" : "Start import"}
      </Button>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}

function RetryRunSection({
  runId,
  token,
  onRetried,
}: {
  runId: string;
  token: string | null;
  onRetried: () => void;
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function handleRetry() {
    if (!token) return;
    setError(null);
    setLoading(true);
    try {
      await apiFetch(`/api/runs/${runId}/retry`, { method: "POST" }, token);
      onRetried();
      router.refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to retry");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
      <h2 className="text-sm font-medium text-gray-700">Retry run</h2>
      <p className="mt-1 text-sm text-gray-500">
        Re-queue this run to try again. The run will be set to QUEUED and processed by the worker.
      </p>
      <Button
        data-testid="run-retry"
        className="mt-3"
        onClick={handleRetry}
        disabled={loading}
      >
        {loading ? "Retrying…" : "Retry"}
      </Button>
      {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
    </div>
  );
}

export default function RunDetailPage() {
  const params = useParams();
  const runId = params.runId as string;
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const [runState, setRunState] = useState<SSERunPayload | null>(null);
  const [sseStatus, setSseStatus] = useState<SSEConnectionStatus>("closed");
  const [eventLog, setEventLog] = useState<EventLogEntry[]>([]);
  const eventIdRef = useRef(0);
  const closeRef = useRef<(() => void) | null>(null);

  const { data: run, isLoading } = useQuery({
    queryKey: ["run", runId],
    queryFn: () => apiFetch<RunDetail>(`/api/runs/${runId}`, {}, token),
    enabled: !!token && !!runId,
  });

  const appendEvent = useCallback((event: string) => {
    setEventLog((prev) => {
      const next = [
        ...prev,
        {
          id: `ev-${++eventIdRef.current}`,
          event,
          time: new Date().toLocaleTimeString("en-US", { hour12: false }),
        },
      ];
      return next.slice(-MAX_EVENT_LOG);
    });
  }, []);

  const { data: dataset } = useQuery({
    queryKey: ["dataset", run?.dataset_id],
    queryFn: () =>
      apiFetch<{ mapping: Record<string, unknown> | null }>(
        `/api/datasets/${run!.dataset_id}`,
        {},
        token
      ),
    enabled: !!token && !!run?.dataset_id && run?.status === "DRAFT",
  });

  const { data: attemptsData } = useQuery({
    queryKey: ["run-attempts", runId],
    queryFn: () =>
      apiFetch<{ items: RunAttempt[] }>(`/api/runs/${runId}/attempts`, {}, token),
    enabled: !!token && !!runId,
  });
  const attempts = attemptsData?.items ?? [];

  useEffect(() => {
    if (!token || !runId) return;
    if (run?.status === "DRAFT") return;
    if (run && isTerminal(run.status)) return;

    const { close } = connectRunEvents({
      runId,
      token,
      onStatus: setSseStatus,
      onEvent(ev) {
        appendEvent(ev.event);
        if (
          ev.event === "run.snapshot" ||
          ev.event === "run.progress" ||
          ev.event === "run.completed"
        ) {
          setRunState(ev.data as SSERunPayload);
        }
        if (ev.event === "run.completed") {
          queryClient.invalidateQueries({ queryKey: ["run", runId] });
        }
      },
    });
    closeRef.current = close;
    return () => {
      closeRef.current?.();
      closeRef.current = null;
    };
  }, [token, runId, run?.status, appendEvent, queryClient]);

  const display = runState ?? run;
  const isLive = !!runState && !isTerminal(display?.status ?? "");

  if (isLoading && !display) {
    return (
      <div className="space-y-4">
        <p className="text-gray-500">Loading run…</p>
      </div>
    );
  }

  if (!display) {
    return (
      <div className="space-y-4">
        <p className="text-gray-500">Run not found.</p>
        <Link href="/datasets" className="text-blue-600 hover:underline">
          Back to datasets
        </Link>
      </div>
    );
  }

  const total = display.total_rows ?? 0;
  const pct =
    total > 0
      ? Math.round((display.processed_rows / total) * 100)
      : display.progress_percent;

  const statusLabel =
    sseStatus === "open"
      ? "SSE connected"
      : sseStatus === "connecting"
        ? "Connecting…"
        : sseStatus === "reconnecting"
          ? "Reconnecting…"
          : isTerminal(display.status)
            ? "Completed"
            : "Closed";

  return (
    <div className="space-y-6">
      <div>
        <Link href="/datasets" className="text-sm text-blue-600 hover:underline">
          ← Datasets
        </Link>
        <div className="mt-2 flex flex-wrap items-center gap-3">
          <h1 className="text-2xl font-semibold">
            Run {display.id.slice(0, 8)}
          </h1>
          <span
            className="rounded-full bg-gray-100 px-3 py-1 text-xs font-medium text-gray-700"
            data-testid="run-sse-status"
          >
            {statusLabel}
          </span>
          {isLive && (
            <span className="text-sm text-blue-600">(live)</span>
          )}
        </div>
        <p className="mt-1 text-sm text-gray-500">
          Status: <span className="font-medium">{display.status}</span>
          {run?.dlq && (
            <span className="ml-2 rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
              DLQ
            </span>
          )}
        </p>
        <Link
          href={`/runs/${runId}/results`}
          className="mt-2 inline-block text-sm text-blue-600 hover:underline"
        >
          View results & exports →
        </Link>
        {display.status === "DRAFT" && (
          <Link
            href={`/runs/${runId}/mapping`}
            className="ml-4 inline-block text-sm text-blue-600 hover:underline"
          >
            Configure mapping →
          </Link>
        )}
      </div>

      {display.status === "DRAFT" && (
        <StartRunSection
          runId={runId}
          datasetId={run?.dataset_id ?? ""}
          hasMapping={!!dataset?.mapping && Object.keys(dataset.mapping).length > 0}
          token={token}
          onStarted={() => queryClient.invalidateQueries({ queryKey: ["run", runId] })}
        />
      )}

      {(display.status === "FAILED" || (run?.dlq === true)) && (
        <RetryRunSection
          runId={runId}
          token={token}
          onRetried={() => {
            queryClient.invalidateQueries({ queryKey: ["run", runId] });
            queryClient.invalidateQueries({ queryKey: ["run-attempts", runId] });
          }}
        />
      )}

      {isTerminal(display.status) && (
        <RerunSection
          runId={runId}
          onRerun={(newRunId) => {
            router.push(`/runs/${newRunId}`);
          }}
        />
      )}

      <div
        className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
        data-testid="run-progress"
      >
        <div className="mb-2 flex justify-between text-sm">
          <span>Progress</span>
          <span>{pct}%</span>
        </div>
        <div className="h-3 w-full overflow-hidden rounded-full bg-gray-200">
          <div
            className="h-full rounded-full bg-blue-600 transition-all duration-300"
            style={{ width: `${pct}%` }}
          />
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
          <div>
            <span className="text-gray-500">Processed</span>
            <p className="font-medium">{display.processed_rows}</p>
          </div>
          <div>
            <span className="text-gray-500">Total</span>
            <p className="font-medium">{display.total_rows ?? "—"}</p>
          </div>
          <div>
            <span className="text-gray-500">Success</span>
            <p className="font-medium text-green-600">{display.success_rows}</p>
          </div>
          <div>
            <span className="text-gray-500">Errors</span>
            <p className="font-medium text-red-600">{display.error_rows}</p>
          </div>
        </div>
      </div>

      {"error_summary" in display && display.error_summary && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">
          {display.error_summary}
        </div>
      )}

      <div
        className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
        data-testid="run-attempts"
      >
        <h2 className="mb-3 text-sm font-medium text-gray-700">Attempt history</h2>
        {attempts.length === 0 ? (
          <p className="text-sm text-gray-500">No attempts yet.</p>
        ) : (
          <ul className="space-y-2">
            {attempts.map((a) => (
              <li
                key={a.id}
                className="flex flex-wrap items-center gap-2 rounded border border-gray-100 bg-gray-50 px-3 py-2 text-sm"
              >
                <span className="font-medium">#{a.attempt_number}</span>
                <span className="text-gray-500">{a.status}</span>
                <span className="text-gray-400">
                  {new Date(a.started_at).toLocaleString()}
                  {a.finished_at && ` → ${new Date(a.finished_at).toLocaleString()}`}
                </span>
                {a.error_message && (
                  <span className="w-full text-red-600">{a.error_message}</span>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <RunEventLog events={eventLog} data-testid="run-event-log" />

      <RunErrorsPreview
        errors={run?.errors ?? []}
        totalErrorCount={display.error_rows}
        runId={runId}
        data-testid="run-errors-preview"
      />
    </div>
  );
}
