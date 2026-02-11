"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

type RunDetail = { id: string; dataset_id: string; status: string };
type HeaderResponse = { columns: string[] };
type DatasetResponse = { id: string; mapping: Record<string, { source: string; format?: string; currency?: boolean; default?: number }> | null };

const CANONICAL_FIELDS = [
  { key: "date", label: "Date", required: true, format: true },
  { key: "campaign", label: "Campaign", required: true },
  { key: "channel", label: "Channel", required: true },
  { key: "spend", label: "Spend", required: true, currency: true },
  { key: "clicks", label: "Clicks", required: false, default: 0 },
  { key: "conversions", label: "Conversions", required: false, default: 0 },
] as const;

const DATE_FORMATS = [
  { value: "YYYY-MM-DD", label: "YYYY-MM-DD" },
  { value: "MM/DD/YYYY", label: "MM/DD/YYYY" },
];

export default function RunMappingPage() {
  const params = useParams();
  const router = useRouter();
  const runId = params.runId as string;
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const [mapping, setMapping] = useState<Record<string, { source: string; format?: string; currency?: boolean; default?: number }>>({});
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const { data: run } = useQuery({
    queryKey: ["run", runId],
    queryFn: () => apiFetch<RunDetail>(`/api/runs/${runId}`, {}, token),
    enabled: !!token && !!runId,
  });

  const datasetId = run?.dataset_id;

  const { data: header } = useQuery({
    queryKey: ["run-header", runId],
    queryFn: () => apiFetch<HeaderResponse>(`/api/runs/${runId}/header`, {}, token),
    enabled: !!token && !!runId,
  });

  const { data: dataset } = useQuery({
    queryKey: ["dataset", datasetId],
    queryFn: () => apiFetch<DatasetResponse>(`/api/datasets/${datasetId}`, {}, token),
    enabled: !!token && !!datasetId,
  });

  const columns = header?.columns ?? [];
  const currentMapping = dataset?.mapping ?? {};

  const saveMutation = useMutation({
    mutationFn: (body: { mapping: Record<string, unknown> }) =>
      apiFetch(`/api/datasets/${datasetId}/mapping`, { method: "PUT", body: JSON.stringify(body) }, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["dataset", datasetId] });
      setSaveMessage("Mapping saved.");
    },
    onError: (e: Error) => setSaveMessage(e.message),
  });

  const startMutation = useMutation({
    mutationFn: () => apiFetch(`/api/runs/${runId}/start`, { method: "POST" }, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["run", runId] });
      router.push(`/runs/${runId}`);
    },
    onError: (e: Error) => setSaveMessage(e.message),
  });

  const formMapping = { ...currentMapping, ...mapping };

  function handleSave() {
    const body: Record<string, { source?: string; format?: string; currency?: boolean; default?: number }> = {};
    for (const f of CANONICAL_FIELDS) {
      const m = formMapping[f.key];
      if (f.required && !m?.source) continue;
      if (m?.source) {
        body[f.key] = { source: m.source };
        if (f.format && m.format) body[f.key].format = m.format;
        if (f.currency && m.currency != null) body[f.key].currency = m.currency;
        if (f.default !== undefined && m.default !== undefined) body[f.key].default = m.default;
      } else if (f.default !== undefined) {
        body[f.key] = { default: formMapping[f.key]?.default ?? f.default };
      }
    }
    saveMutation.mutate({ mapping: body });
  }

  function handleStart() {
    startMutation.mutate();
  }

  if (!run) {
    return (
      <div className="space-y-4">
        <p className="text-gray-500">Loading…</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link href={`/runs/${runId}`} className="text-sm text-blue-600 hover:underline">
          ← Run detail
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">Column mapping</h1>
        <p className="mt-1 text-sm text-gray-500">
          Map CSV columns to canonical fields. Required: date, campaign, channel, spend.
        </p>
      </div>

      {columns.length === 0 ? (
        <p className="text-gray-500">No header columns (file may be empty or missing).</p>
      ) : (
        <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <p className="mb-3 text-sm text-gray-600">
            Detected columns: {columns.join(", ")}
          </p>
          <div className="space-y-3">
            {CANONICAL_FIELDS.map((f) => (
              <div key={f.key} className="flex flex-wrap items-center gap-2">
                <label className="w-28 text-sm font-medium text-gray-700">
                  {f.label} {f.required && "*"}
                </label>
                <select
                  data-testid={
                    f.key === "date"
                      ? "mapping-date-select"
                      : f.key === "campaign"
                        ? "mapping-campaign-select"
                        : f.key === "channel"
                          ? "mapping-channel-select"
                          : f.key === "spend"
                            ? "mapping-spend-select"
                            : undefined
                  }
                  className="rounded border border-gray-300 px-2 py-1 text-sm"
                  value={formMapping[f.key]?.source ?? ""}
                  onChange={(e) =>
                    setMapping((prev) => ({
                      ...prev,
                      [f.key]: { ...formMapping[f.key], source: e.target.value },
                    }))
                  }
                >
                  <option value="">— Select column —</option>
                  {columns.map((c) => (
                    <option key={c} value={c}>
                      {c}
                    </option>
                  ))}
                </select>
                {f.format && (
                  <select
                    className="rounded border border-gray-300 px-2 py-1 text-sm"
                    value={formMapping[f.key]?.format ?? "YYYY-MM-DD"}
                    onChange={(e) =>
                      setMapping((prev) => ({
                        ...prev,
                        [f.key]: { ...formMapping[f.key], source: formMapping[f.key]?.source ?? "", format: e.target.value },
                      }))
                    }
                  >
                    {DATE_FORMATS.map((d) => (
                      <option key={d.value} value={d.value}>
                        {d.label}
                      </option>
                    ))}
                  </select>
                )}
                {f.currency && (
                  <label className="flex items-center gap-1 text-sm">
                    <input
                      type="checkbox"
                      checked={formMapping[f.key]?.currency ?? true}
                      onChange={(e) =>
                        setMapping((prev) => ({
                          ...prev,
                          [f.key]: { ...formMapping[f.key], source: formMapping[f.key]?.source ?? "", currency: e.target.checked },
                        }))
                      }
                    />
                    Currency ($)
                  </label>
                )}
                {f.default !== undefined && (
                  <>
                    <span className="text-sm text-gray-500">Default:</span>
                    <Input
                      type="number"
                      className="w-20"
                      value={formMapping[f.key]?.default ?? f.default}
                      onChange={(e) =>
                        setMapping((prev) => ({
                          ...prev,
                          [f.key]: { ...formMapping[f.key], source: formMapping[f.key]?.source ?? "", default: Number(e.target.value) || 0 },
                        }))
                      }
                    />
                  </>
                )}
              </div>
            ))}
          </div>
          <div className="mt-4 flex gap-2">
            <Button data-testid="mapping-save" onClick={handleSave} disabled={saveMutation.isPending}>
              {saveMutation.isPending ? "Saving…" : "Save mapping"}
            </Button>
            <Button
              data-testid="run-start"
              variant="secondary"
              onClick={handleStart}
              disabled={startMutation.isPending || !dataset?.mapping || Object.keys(dataset.mapping).length === 0}
            >
              {startMutation.isPending ? "Starting…" : "Start import"}
            </Button>
          </div>
          {saveMessage && <p className="mt-2 text-sm text-gray-600">{saveMessage}</p>}
        </div>
      )}
    </div>
  );
}
