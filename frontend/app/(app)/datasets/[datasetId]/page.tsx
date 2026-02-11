"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

type RunSummary = {
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
  schema_version: number | null;
};

type DatasetWithRuns = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
  runs: RunSummary[];
};

export default function DatasetDetailPage() {
  const params = useParams();
  const router = useRouter();
  const datasetId = params.datasetId as string;
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);

  const { data: dataset, isLoading } = useQuery({
    queryKey: ["dataset", datasetId],
    queryFn: () =>
      apiFetch<DatasetWithRuns>(`/api/datasets/${datasetId}`, {}, token),
    enabled: !!token && !!datasetId,
  });

  const uploadMutation = useMutation({
    mutationFn: async (file: File) => {
      const form = new FormData();
      form.append("file", file);
      const run = await apiFetch<RunSummary>(
        `/api/datasets/${datasetId}/uploads`,
        {
          method: "POST",
          body: form,
        },
        token
      );
      return run;
    },
    onSuccess: (run) => {
      queryClient.invalidateQueries({ queryKey: ["dataset", datasetId] });
      setUploadError(null);
      router.push(`/runs/${run.id}/mapping`);
    },
    onError: (err: Error) => {
      setUploadError(err.message);
    },
  });

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploadError(null);
    uploadMutation.mutate(file);
    e.target.value = "";
  }

  if (isLoading || !dataset) {
    return (
      <div className="space-y-4">
        <Link href="/datasets" className="text-sm text-blue-600 hover:underline">
          ← Datasets
        </Link>
        <p className="text-gray-500">Loading…</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link href="/datasets" className="text-sm text-blue-600 hover:underline">
          ← Datasets
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">{dataset.name}</h1>
        {dataset.description && (
          <p className="mt-1 text-gray-500">{dataset.description}</p>
        )}
      </div>

      {/* Navigation Tabs */}
      <div className="border-b border-gray-200">
        <nav className="flex gap-4">
          <Link
            href={`/datasets/${datasetId}`}
            className="px-4 py-2 border-b-2 border-blue-600 text-blue-600 font-medium"
          >
            Overview
          </Link>
          <Link
            href={`/datasets/${datasetId}/schema`}
            className="px-4 py-2 text-gray-600 hover:text-gray-900"
          >
            Schema
          </Link>
        </nav>
      </div>

      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <h2 className="mb-3 text-sm font-medium text-gray-700">
          Upload CSV
        </h2>
        <input
          ref={fileInputRef}
          type="file"
          accept=".csv"
          className="hidden"
          data-testid="dataset-file-input"
          onChange={handleFileChange}
        />
        <Button
          data-testid="dataset-upload"
          onClick={() => fileInputRef.current?.click()}
          disabled={uploadMutation.isPending}
        >
          {uploadMutation.isPending ? "Uploading…" : "Choose CSV file"}
        </Button>
        {uploadError && (
          <p className="mt-2 text-sm text-red-600">{uploadError}</p>
        )}
      </div>

      <div>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-medium text-gray-700">
            Recent runs
          </h2>
          {dataset.runs.filter((r) => r.status === "SUCCEEDED").length >= 2 && (
            <Link
              href={`/datasets/${datasetId}/compare`}
              className="text-sm text-blue-600 hover:underline"
              data-testid="compare-runs-link"
            >
              Compare runs
            </Link>
          )}
        </div>
        {dataset.runs.length === 0 ? (
          <p className="text-sm text-gray-500">No runs yet.</p>
        ) : (
          <ul className="space-y-2">
            {dataset.runs.map((run) => (
              <li key={run.id}>
                <Link
                  href={`/runs/${run.id}`}
                  className="block rounded border border-gray-200 bg-white px-4 py-3 transition hover:border-gray-300"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">
                      {run.status} – {run.processed_rows} /{" "}
                      {run.total_rows ?? "?"} rows
                      {run.schema_version && (
                        <span className="ml-2 text-xs text-gray-500">
                          (Schema v{run.schema_version})
                        </span>
                      )}
                    </span>
                    <span className="text-xs text-gray-500">
                      {new Date(run.created_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="mt-1 text-xs text-gray-500">
                    ✓ {run.success_rows} success · ✗ {run.error_rows} errors
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}
