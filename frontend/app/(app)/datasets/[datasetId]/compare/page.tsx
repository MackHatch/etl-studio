"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { useCompareRuns } from "@/features/compare/queries";
import { Button } from "@/components/ui/Button";

type RunSummary = {
  id: string;
  dataset_id: string;
  status: string;
  schema_version: number | null;
  finished_at: string | null;
};

type DatasetWithRuns = {
  id: string;
  name: string;
  runs: RunSummary[];
};

export default function CompareRunsPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const datasetId = params.datasetId as string;
  const { token } = useAuth();

  const urlLeft = searchParams.get("leftRunId");
  const urlRight = searchParams.get("rightRunId");

  const { data: dataset } = useQuery({
    queryKey: ["dataset", datasetId],
    queryFn: () =>
      apiFetch<DatasetWithRuns>(`/api/datasets/${datasetId}`, {}, token),
    enabled: !!token && !!datasetId,
  });

  const succeededRuns = dataset?.runs.filter((r) => r.status === "SUCCEEDED") ?? [];
  
  // Default: URL params > last two succeeded runs
  const defaultLeft = succeededRuns.length >= 2 ? succeededRuns[succeededRuns.length - 2]?.id : null;
  const defaultRight = succeededRuns.length >= 1 ? succeededRuns[succeededRuns.length - 1]?.id : null;
  
  const [leftRunId, setLeftRunId] = useState<string | null>(urlLeft || defaultLeft);
  const [rightRunId, setRightRunId] = useState<string | null>(urlRight || defaultRight);

  useEffect(() => {
    if (urlLeft && dataset?.runs.some((r) => r.id === urlLeft)) setLeftRunId(urlLeft);
    if (urlRight && dataset?.runs.some((r) => r.id === urlRight)) setRightRunId(urlRight);
  }, [dataset?.runs, urlLeft, urlRight]);

  const { data: compareData, isLoading, error } = useCompareRuns(
    datasetId,
    leftRunId,
    rightRunId
  );

  if (!dataset) {
    return (
      <div className="space-y-4">
        <Link href={`/datasets/${datasetId}`} className="text-sm text-blue-600 hover:underline">
          ← Dataset
        </Link>
        <p className="text-gray-500">Loading…</p>
      </div>
    );
  }

  if (succeededRuns.length < 2) {
    return (
      <div className="space-y-4">
        <Link href={`/datasets/${datasetId}`} className="text-sm text-blue-600 hover:underline">
          ← Dataset
        </Link>
        <div className="rounded border border-yellow-200 bg-yellow-50 p-4">
          <p className="text-sm text-yellow-800">
            Need at least 2 succeeded runs to compare. Currently have {succeededRuns.length}.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <Link href={`/datasets/${datasetId}`} className="text-sm text-blue-600 hover:underline">
          ← Dataset
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">Compare Runs</h1>
        <p className="mt-1 text-sm text-gray-600">{dataset.name}</p>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Left Run
          </label>
          <select
            value={leftRunId || ""}
            onChange={(e) => setLeftRunId(e.target.value || null)}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            data-testid="compare-left-select"
          >
            <option value="">Select run...</option>
            {succeededRuns.map((run) => (
              <option key={run.id} value={run.id}>
                {run.id.slice(0, 8)}... (Schema v{run.schema_version ?? "?"}) -{" "}
                {run.finished_at
                  ? new Date(run.finished_at).toLocaleDateString()
                  : "N/A"}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Right Run
          </label>
          <select
            value={rightRunId || ""}
            onChange={(e) => setRightRunId(e.target.value || null)}
            className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
            data-testid="compare-right-select"
          >
            <option value="">Select run...</option>
            {succeededRuns.map((run) => (
              <option key={run.id} value={run.id}>
                {run.id.slice(0, 8)}... (Schema v{run.schema_version ?? "?"}) -{" "}
                {run.finished_at
                  ? new Date(run.finished_at).toLocaleDateString()
                  : "N/A"}
              </option>
            ))}
          </select>
        </div>
      </div>

      {error && (
        <div className="rounded border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-800">
            Error loading comparison: {error instanceof Error ? error.message : "Unknown error"}
          </p>
        </div>
      )}

      {isLoading && (
        <p className="text-gray-500">Loading comparison...</p>
      )}

      {compareData && (
        <div className="space-y-6">
          {/* KPI Diff Cards */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4" data-testid="compare-diff-cards">
            <div className="rounded border border-gray-200 bg-white p-4">
              <div className="text-sm text-gray-600">Spend</div>
              <div className="mt-1 text-lg font-semibold">
                ${compareData.diff.spend_total.right.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </div>
              <div className={`text-xs mt-1 ${compareData.diff.spend_total.delta >= 0 ? "text-green-600" : "text-red-600"}`}>
                {compareData.diff.spend_total.delta >= 0 ? "+" : ""}
                ${compareData.diff.spend_total.delta.toLocaleString(undefined, {
                  minimumFractionDigits: 2,
                  maximumFractionDigits: 2,
                })}
              </div>
            </div>

            <div className="rounded border border-gray-200 bg-white p-4">
              <div className="text-sm text-gray-600">Clicks</div>
              <div className="mt-1 text-lg font-semibold">
                {compareData.diff.clicks_total.right.toLocaleString()}
              </div>
              <div className={`text-xs mt-1 ${compareData.diff.clicks_total.delta >= 0 ? "text-green-600" : "text-red-600"}`}>
                {compareData.diff.clicks_total.delta >= 0 ? "+" : ""}
                {compareData.diff.clicks_total.delta.toLocaleString()}
              </div>
            </div>

            <div className="rounded border border-gray-200 bg-white p-4">
              <div className="text-sm text-gray-600">Conversions</div>
              <div className="mt-1 text-lg font-semibold">
                {compareData.diff.conversions_total.right.toLocaleString()}
              </div>
              <div className={`text-xs mt-1 ${compareData.diff.conversions_total.delta >= 0 ? "text-green-600" : "text-red-600"}`}>
                {compareData.diff.conversions_total.delta >= 0 ? "+" : ""}
                {compareData.diff.conversions_total.delta.toLocaleString()}
              </div>
            </div>
          </div>

          {/* Row counts */}
          <div className="rounded border border-gray-200 bg-white p-4">
            <h3 className="text-sm font-medium text-gray-700 mb-2">Row Comparison</h3>
            <div className="grid grid-cols-3 gap-4 text-sm">
              <div>
                <span className="text-gray-600">Success rows:</span>{" "}
                <span className="font-medium">{compareData.diff.success_rows >= 0 ? "+" : ""}{compareData.diff.success_rows}</span>
              </div>
              <div>
                <span className="text-gray-600">Error rows:</span>{" "}
                <span className="font-medium">{compareData.diff.error_rows >= 0 ? "+" : ""}{compareData.diff.error_rows}</span>
              </div>
              {compareData.diff.total_rows !== null && (
                <div>
                  <span className="text-gray-600">Total rows:</span>{" "}
                  <span className="font-medium">{compareData.diff.total_rows >= 0 ? "+" : ""}{compareData.diff.total_rows}</span>
                </div>
              )}
            </div>
          </div>

          {/* Top changed campaigns */}
          {compareData.diff.top_changed_campaigns.length > 0 && (
            <div className="rounded border border-gray-200 bg-white p-4">
              <h3 className="text-sm font-medium text-gray-700 mb-3">Top Changed Campaigns</h3>
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500 uppercase">
                        Campaign
                      </th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                        Left Spend
                      </th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                        Right Spend
                      </th>
                      <th className="px-4 py-2 text-right text-xs font-medium text-gray-500 uppercase">
                        Delta
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {compareData.diff.top_changed_campaigns.map((campaign) => (
                      <tr key={campaign.campaign}>
                        <td className="px-4 py-2 text-sm">{campaign.campaign}</td>
                        <td className="px-4 py-2 text-sm text-right">
                          ${campaign.spend_left.toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}
                        </td>
                        <td className="px-4 py-2 text-sm text-right">
                          ${campaign.spend_right.toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}
                        </td>
                        <td className={`px-4 py-2 text-sm text-right font-medium ${
                          campaign.delta >= 0 ? "text-green-600" : "text-red-600"
                        }`}>
                          {campaign.delta >= 0 ? "+" : ""}
                          ${campaign.delta.toLocaleString(undefined, {
                            minimumFractionDigits: 2,
                            maximumFractionDigits: 2,
                          })}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* Links to runs */}
          <div className="flex gap-4">
            <Link
              href={`/runs/${compareData.left_run.id}`}
              className="text-sm text-blue-600 hover:underline"
            >
              View left run →
            </Link>
            <Link
              href={`/runs/${compareData.right_run.id}`}
              className="text-sm text-blue-600 hover:underline"
            >
              View right run →
            </Link>
          </div>
        </div>
      )}
    </div>
  );
}
