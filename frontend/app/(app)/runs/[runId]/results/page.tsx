"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { apiFetch, baseURL } from "@/lib/api";
import { downloadBlob } from "@/lib/download";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

type RecordRow = {
  id: string;
  run_id: string;
  row_number: number;
  date: string;
  campaign: string;
  channel: string;
  spend: string;
  clicks: number;
  conversions: number;
  created_at: string;
};

type RecordsResponse = {
  items: RecordRow[];
  page: number;
  page_size: number;
  total: number;
};

const PAGE_SIZE = 20;

export default function RunResultsPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const runId = params.runId as string;
  const { token } = useAuth();
  const [search, setSearch] = useState(searchParams.get("search") ?? "");
  const [channel, setChannel] = useState(searchParams.get("channel") ?? "");
  const [minSpend, setMinSpend] = useState(searchParams.get("minSpend") ?? "");
  const [page, setPage] = useState(Number(searchParams.get("page")) || 1);

  const { data, isLoading } = useQuery({
    queryKey: ["run-records", runId, page, search, channel, minSpend],
    queryFn: () => {
      const sp = new URLSearchParams();
      if (page > 1) sp.set("page", String(page));
      sp.set("pageSize", String(PAGE_SIZE));
      if (search) sp.set("search", search);
      if (channel) sp.set("channel", channel);
      if (minSpend) sp.set("minSpend", minSpend);
      return apiFetch<RecordsResponse>(
        `/api/runs/${runId}/records?${sp.toString()}`,
        {},
        token
      );
    },
    enabled: !!token && !!runId,
  });

  async function handleExportRecords() {
    if (!token) return;
    const res = await fetch(`${baseURL}/api/runs/${runId}/records.csv`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return;
    const blob = await res.blob();
    downloadBlob(`run-${runId}-records.csv`, blob);
  }

  async function handleExportErrors() {
    if (!token) return;
    const res = await fetch(`${baseURL}/api/runs/${runId}/errors.csv`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return;
    const blob = await res.blob();
    downloadBlob(`run-${runId}-errors.csv`, blob);
  }

  const totalPages = data ? Math.ceil(data.total / PAGE_SIZE) : 0;

  return (
    <div className="space-y-6">
      <div>
        <Link href={`/runs/${runId}`} className="text-sm text-blue-600 hover:underline">
          ← Run detail
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">Results</h1>
        <p className="mt-1 text-sm text-gray-500">Run {runId.slice(0, 8)}</p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button
          data-testid="export-records"
          onClick={handleExportRecords}
          disabled={!data?.total}
        >
          Download cleaned CSV
        </Button>
        <Button
          data-testid="export-errors"
          variant="secondary"
          onClick={handleExportErrors}
        >
          Download errors CSV
        </Button>
      </div>

      <div className="flex flex-wrap gap-4">
        <div className="w-48">
          <label className="mb-1 block text-sm text-gray-700">Search campaign</label>
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Campaign..."
          />
        </div>
        <div className="w-32">
          <label className="mb-1 block text-sm text-gray-700">Channel</label>
          <Input
            value={channel}
            onChange={(e) => setChannel(e.target.value)}
            placeholder="Channel"
          />
        </div>
        <div className="w-28">
          <label className="mb-1 block text-sm text-gray-700">Min spend</label>
          <Input
            type="number"
            min="0"
            step="0.01"
            value={minSpend}
            onChange={(e) => setMinSpend(e.target.value)}
            placeholder="0"
          />
        </div>
        <div className="flex items-end">
          <Button
            variant="secondary"
            onClick={() => setPage(1)}
          >
            Apply
          </Button>
        </div>
      </div>

      {isLoading ? (
        <p className="text-gray-500">Loading…</p>
      ) : !data ? (
        <p className="text-gray-500">No data.</p>
      ) : (
        <>
          <div
            className="overflow-x-auto rounded-lg border border-gray-200 bg-white shadow-sm"
            data-testid="results-table"
          >
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50">
                  <th className="px-4 py-2 font-medium text-gray-700">Row</th>
                  <th className="px-4 py-2 font-medium text-gray-700">Date</th>
                  <th className="px-4 py-2 font-medium text-gray-700">Campaign</th>
                  <th className="px-4 py-2 font-medium text-gray-700">Channel</th>
                  <th className="px-4 py-2 font-medium text-gray-700">Spend</th>
                  <th className="px-4 py-2 font-medium text-gray-700">Clicks</th>
                  <th className="px-4 py-2 font-medium text-gray-700">Conversions</th>
                </tr>
              </thead>
              <tbody>
                {data.items.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-gray-500">
                      No records match filters.
                    </td>
                  </tr>
                ) : (
                  data.items.map((r) => (
                    <tr key={r.id} className="border-b border-gray-100 last:border-0">
                      <td className="px-4 py-2 font-mono">{r.row_number}</td>
                      <td className="px-4 py-2">{r.date}</td>
                      <td className="px-4 py-2">{r.campaign}</td>
                      <td className="px-4 py-2">{r.channel}</td>
                      <td className="px-4 py-2">{r.spend}</td>
                      <td className="px-4 py-2">{r.clicks}</td>
                      <td className="px-4 py-2">{r.conversions}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          <div className="flex items-center justify-between text-sm text-gray-600">
            <span>
              Page {data.page} of {totalPages || 1} · {data.total} total
            </span>
            <div className="flex gap-2">
              <Button
                variant="secondary"
                disabled={page <= 1}
                onClick={() => setPage((p) => Math.max(1, p - 1))}
              >
                Previous
              </Button>
              <Button
                variant="secondary"
                disabled={page >= totalPages}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </Button>
            </div>
          </div>
        </>
      )}
    </div>
  );
}
