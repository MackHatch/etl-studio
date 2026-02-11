"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { connectAdminRunsEvents, type SSEConnectionStatus } from "@/lib/sse";

type AdminRunItem = {
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
};

type AdminRunsResponse = {
  items: AdminRunItem[];
  page: number;
  page_size: number;
  total: number;
};

const STATUS_OPTIONS = [
  { value: "", label: "All" },
  { value: "DRAFT", label: "Draft" },
  { value: "QUEUED", label: "Queued" },
  { value: "RUNNING", label: "Running" },
  { value: "SUCCEEDED", label: "Succeeded" },
  { value: "FAILED", label: "Failed" },
];

export default function AdminRunsPage() {
  const router = useRouter();
  const { token, user } = useAuth();
  const queryClient = useQueryClient();
  const closeRef = useRef<(() => void) | null>(null);

  useEffect(() => {
    if (!user || user.role !== "ADMIN") {
      router.replace("/datasets");
    }
  }, [user, router]);

  const [statusFilter, setStatusFilter] = useState("");
  const [dlqFilter, setDlqFilter] = useState<boolean | "">("");
  const [searchQ, setSearchQ] = useState("");
  const [page, setPage] = useState(1);
  const pageSize = 20;

  const queryParams = new URLSearchParams();
  if (statusFilter) queryParams.set("status", statusFilter);
  if (dlqFilter !== "") queryParams.set("dlq", String(dlqFilter));
  if (searchQ.trim()) queryParams.set("q", searchQ.trim());
  queryParams.set("page", String(page));
  queryParams.set("pageSize", String(pageSize));

  const { data, isLoading } = useQuery({
    queryKey: ["admin-runs", statusFilter, dlqFilter, searchQ.trim(), page, pageSize],
    queryFn: () =>
      apiFetch<AdminRunsResponse>(
        `/api/admin/runs?${queryParams.toString()}`,
        {},
        token
      ),
    enabled: !!token && !!user && user.role === "ADMIN",
  });

  const [sseStatus, setSseStatus] = useState<SSEConnectionStatus>("closed");

  useEffect(() => {
    if (!token || user?.role !== "ADMIN") return;
    const { close } = connectAdminRunsEvents({
      token,
      onStatus: setSseStatus,
      onEvent(ev) {
        if (ev.event === "runs.snapshot" && ev.data.items) {
          queryClient.setQueryData(
            ["admin-runs", "", "", "", 1, pageSize],
            (prev: AdminRunsResponse | undefined) =>
              prev
                ? { ...prev, items: ev.data.items!, total: ev.data.items!.length }
                : {
                    items: ev.data.items!,
                    page: 1,
                    page_size: pageSize,
                    total: ev.data.items!.length,
                  }
          );
        }
        if (ev.event === "runs.changed" && ev.data.items?.length) {
          queryClient.invalidateQueries({ queryKey: ["admin-runs"] });
        }
      },
    });
    closeRef.current = close;
    return () => {
      closeRef.current?.();
      closeRef.current = null;
    };
  }, [token, user?.role, queryClient, pageSize]);

  if (!user) {
    return (
      <div className="space-y-4">
        <p className="text-gray-500">Loading…</p>
      </div>
    );
  }
  if (user.role !== "ADMIN") {
    return null;
  }

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <Link href="/datasets" className="text-sm text-blue-600 hover:underline">
            ← Datasets
          </Link>
          <h1 className="mt-2 text-2xl font-semibold">Admin: Runs</h1>
        </div>
        <span
          className={`rounded-full px-3 py-1 text-xs font-medium ${
            sseStatus === "open"
              ? "bg-green-100 text-green-800"
              : sseStatus === "reconnecting" || sseStatus === "connecting"
                ? "bg-amber-100 text-amber-800"
                : "bg-gray-100 text-gray-600"
          }`}
        >
          {sseStatus === "open"
            ? "Live"
            : sseStatus === "reconnecting"
              ? "Reconnecting…"
              : sseStatus === "connecting"
                ? "Connecting…"
                : "Off"}
        </span>
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-lg border border-gray-200 bg-white p-3">
        <label className="flex items-center gap-2 text-sm">
          <span className="text-gray-600">Status</span>
          <select
            data-testid="admin-runs-filter-status"
            className="rounded border border-gray-300 px-2 py-1 text-sm"
            value={statusFilter}
            onChange={(e) => {
              setStatusFilter(e.target.value);
              setPage(1);
            }}
          >
            {STATUS_OPTIONS.map((o) => (
              <option key={o.value || "all"} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-gray-600">DLQ</span>
          <select
            data-testid="admin-runs-filter-dlq"
            className="rounded border border-gray-300 px-2 py-1 text-sm"
            value={dlqFilter === "" ? "" : dlqFilter ? "true" : "false"}
            onChange={(e) => {
              const v = e.target.value;
              setDlqFilter(v === "" ? "" : v === "true");
              setPage(1);
            }}
          >
            <option value="">All</option>
            <option value="true">Yes</option>
            <option value="false">No</option>
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-gray-600">Dataset</span>
          <input
            type="search"
            placeholder="Search by name"
            className="rounded border border-gray-300 px-2 py-1 text-sm"
            value={searchQ}
            onChange={(e) => {
              setSearchQ(e.target.value);
              setPage(1);
            }}
          />
        </label>
      </div>

      <div
        className="overflow-hidden rounded-lg border border-gray-200 bg-white"
        data-testid="admin-runs-table"
      >
        {isLoading ? (
          <div className="p-8 text-center text-gray-500">Loading runs…</div>
        ) : items.length === 0 ? (
          <div className="p-8 text-center text-gray-500">No runs match the filters.</div>
        ) : (
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Run</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Dataset</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Status</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Progress</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Attempts</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">DLQ</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Updated</th>
                <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Last error</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {items.map((run) => (
                <tr
                  key={run.id}
                  className="cursor-pointer hover:bg-gray-50"
                  onClick={() => router.push(`/runs/${run.id}`)}
                >
                  <td className="whitespace-nowrap px-4 py-2 text-sm">
                    <Link
                      href={`/runs/${run.id}`}
                      className="text-blue-600 hover:underline"
                      onClick={(e) => e.stopPropagation()}
                    >
                      {run.id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="px-4 py-2 text-sm text-gray-700">{run.dataset_name}</td>
                  <td className="px-4 py-2 text-sm">
                    <span
                      className={`rounded px-2 py-0.5 text-xs ${
                        run.status === "SUCCEEDED"
                          ? "bg-green-100 text-green-800"
                          : run.status === "FAILED"
                            ? "bg-red-100 text-red-800"
                            : run.status === "RUNNING"
                              ? "bg-blue-100 text-blue-800"
                              : "bg-gray-100 text-gray-700"
                      }`}
                    >
                      {run.status}
                    </span>
                  </td>
                  <td className="px-4 py-2 text-sm text-gray-700">
                    {run.progress_percent}% ({run.processed_rows}
                    {run.total_rows != null ? ` / ${run.total_rows}` : ""})
                  </td>
                  <td className="px-4 py-2 text-sm text-gray-700">{run.attempt_count}</td>
                  <td className="px-4 py-2 text-sm">{run.dlq ? "Yes" : "—"}</td>
                  <td className="whitespace-nowrap px-4 py-2 text-sm text-gray-500">
                    {new Date(run.updated_at).toLocaleString()}
                  </td>
                  <td className="max-w-xs truncate px-4 py-2 text-sm text-red-600" title={run.last_error ?? undefined}>
                    {run.last_error ?? "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {total > pageSize && (
        <div className="flex items-center gap-2 text-sm">
          <button
            type="button"
            className="rounded border border-gray-300 px-2 py-1 disabled:opacity-50"
            disabled={page <= 1}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </button>
          <span className="text-gray-600">
            Page {page} of {Math.ceil(total / pageSize)}
          </span>
          <button
            type="button"
            className="rounded border border-gray-300 px-2 py-1 disabled:opacity-50"
            disabled={page >= Math.ceil(total / pageSize)}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}
