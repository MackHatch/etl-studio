"use client";

import Link from "next/link";
import { useState } from "react";
import { useAuth } from "@/lib/auth";
import { useDatasets, useAnalyticsSummary, useAnalyticsAnomalies } from "@/features/analytics/queries";
import { SpendByDayChart } from "@/components/analytics/SpendByDayChart";
import { ChannelBarChart } from "@/components/analytics/ChannelBarChart";

const RANGE_OPTIONS = [
  { value: "7d", label: "Last 7 days" },
  { value: "30d", label: "Last 30 days" },
  { value: "90d", label: "Last 90 days" },
];

export default function AnalyticsPage() {
  const { token } = useAuth();
  const [datasetId, setDatasetId] = useState<string>("");
  const [range, setRange] = useState("30d");

  const { data: datasets } = useDatasets(token);
  const { data: summary, isLoading: summaryLoading } = useAnalyticsSummary(
    datasetId || null,
    range,
    token
  );
  const { data: anomaliesData } = useAnalyticsAnomalies(
    datasetId || null,
    range,
    token
  );

  const byDay = summary?.byDay ?? summary?.by_day ?? [];
  const byChannel = summary?.byChannel ?? summary?.by_channel ?? [];
  const totals = summary?.totals ?? { spend: 0, clicks: 0, conversions: 0 };
  const anomalies = anomaliesData?.items ?? [];

  return (
    <div className="space-y-6">
      <div>
        <Link href="/datasets" className="text-sm text-blue-600 hover:underline">
          ← Datasets
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">Analytics</h1>
        <p className="mt-1 text-sm text-gray-500">
          Summaries and anomaly flags for imported marketing data.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-4 rounded-lg border border-gray-200 bg-white p-4">
        <label className="flex items-center gap-2 text-sm">
          <span className="text-gray-600">Dataset</span>
          <select
            className="rounded border border-gray-300 px-2 py-1 text-sm"
            value={datasetId}
            onChange={(e) => setDatasetId(e.target.value)}
          >
            <option value="">Select dataset</option>
            {(datasets ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-gray-600">Range</span>
          <select
            data-testid="analytics-range"
            className="rounded border border-gray-300 px-2 py-1 text-sm"
            value={range}
            onChange={(e) => setRange(e.target.value)}
          >
            {RANGE_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </label>
      </div>

      {!datasetId ? (
        <p className="text-gray-500">Select a dataset to view analytics.</p>
      ) : summaryLoading ? (
        <p className="text-gray-500">Loading…</p>
      ) : (
        <>
          <div
            className="grid grid-cols-1 gap-4 sm:grid-cols-3"
            data-testid="analytics-kpis"
          >
            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <p className="text-sm text-gray-500">Total spend</p>
              <p className="mt-1 text-2xl font-semibold">
                ${totals.spend.toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <p className="text-sm text-gray-500">Total clicks</p>
              <p className="mt-1 text-2xl font-semibold">
                {totals.clicks.toLocaleString()}
              </p>
            </div>
            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <p className="text-sm text-gray-500">Total conversions</p>
              <p className="mt-1 text-2xl font-semibold">
                {totals.conversions.toLocaleString()}
              </p>
            </div>
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <h2 className="mb-3 text-sm font-medium text-gray-700">Spend by day</h2>
              <SpendByDayChart data={byDay} />
            </div>
            <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
              <h2 className="mb-3 text-sm font-medium text-gray-700">Spend by channel</h2>
              <ChannelBarChart data={byChannel} />
            </div>
          </div>

          <div
            className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
            data-testid="analytics-anomalies"
          >
            <h2 className="mb-3 text-sm font-medium text-gray-700">Spend anomalies</h2>
            <p className="mb-3 text-xs text-gray-500">
              Days where spend is more than 3 standard deviations above the channel mean.
            </p>
            {anomalies.length === 0 ? (
              <p className="text-sm text-gray-500">No anomalies in this range.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-gray-200 text-sm">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Date</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Channel</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Spend</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Mean</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Std</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Z-score</th>
                      <th className="px-4 py-2 text-left text-xs font-medium text-gray-500">Flag</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-200">
                    {anomalies.map((a, i) => (
                      <tr key={`${a.date}-${a.channel}-${i}`}>
                        <td className="whitespace-nowrap px-4 py-2 text-gray-700">
                          {new Date(a.date).toLocaleDateString()}
                        </td>
                        <td className="px-4 py-2 text-gray-700">{a.channel}</td>
                        <td className="px-4 py-2 text-gray-700">
                          ${a.spend.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-4 py-2 text-gray-500">
                          ${a.channel_mean.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-4 py-2 text-gray-500">
                          ${a.channel_std.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                        </td>
                        <td className="px-4 py-2 text-gray-600">{a.z_score.toFixed(2)}</td>
                        <td className="px-4 py-2">
                          <span className="inline-flex rounded bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
                            Spike
                          </span>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
