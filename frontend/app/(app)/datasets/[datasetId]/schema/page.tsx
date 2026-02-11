"use client";

import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { RulesEditor, Rules } from "@/components/schema/RulesEditor";
import { useActiveSchema, useSchemaVersions, usePublishSchema } from "@/features/schema/queries";

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

type HeaderResponse = { columns: string[] };

export default function SchemaPage() {
  const params = useParams();
  const router = useRouter();
  const datasetId = params.datasetId as string;
  const { token } = useAuth();

  const { data: activeSchema, isLoading: loadingActive, error: activeError } = useActiveSchema(datasetId);
  const { data: versionsData, isLoading: loadingVersions } = useSchemaVersions(datasetId);
  const publishMutation = usePublishSchema(datasetId);

  // Get a sample run to fetch header columns
  const { data: dataset } = useQuery({
    queryKey: ["dataset", datasetId],
    queryFn: () => apiFetch(`/api/datasets/${datasetId}`, {}, token),
    enabled: !!token && !!datasetId,
  });

  const sampleRunId = dataset?.runs?.[0]?.id;
  const { data: header } = useQuery({
    queryKey: ["run-header", sampleRunId],
    queryFn: () => apiFetch<HeaderResponse>(`/api/runs/${sampleRunId}/header`, {}, token),
    enabled: !!token && !!sampleRunId,
  });

  const columns = header?.columns ?? [];

  const [mapping, setMapping] = useState<Record<string, any>>(currentMapping);
  const [rules, setRules] = useState<Rules>(currentRules);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);

  const formMapping = { ...currentMapping, ...mapping };

  function handlePublish() {
    const bodyMapping: Record<string, any> = {};
    for (const f of CANONICAL_FIELDS) {
      const m = formMapping[f.key];
      if (f.required && !m?.source) continue;
      if (m?.source) {
        bodyMapping[f.key] = { source: m.source };
        if (f.format && m.format) bodyMapping[f.key].format = m.format;
        if (f.currency && m.currency != null) bodyMapping[f.key].currency = m.currency;
        if (f.default !== undefined && m.default !== undefined) bodyMapping[f.key].default = m.default;
      } else if (f.default !== undefined) {
        bodyMapping[f.key] = { default: formMapping[f.key]?.default ?? f.default };
      }
    }

    publishMutation.mutate(
      { mapping: bodyMapping, rules },
      {
        onSuccess: () => {
          setSaveMessage("Schema published successfully!");
          setTimeout(() => setSaveMessage(null), 3000);
        },
        onError: (e: Error) => setSaveMessage(e.message),
      }
    );
  }

  if (loadingActive || loadingVersions) {
    return <div className="p-6">Loading...</div>;
  }

  // If no active schema exists yet, initialize with empty values
  const currentMapping = activeSchema?.mapping ?? {};
  const currentRules = activeSchema?.rules ?? {};

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <div className="mb-6">
        <Link href={`/datasets/${datasetId}`} className="text-blue-600 hover:underline">
          ← Back to Dataset
        </Link>
        <h1 className="text-2xl font-bold mt-2">Schema & Rules</h1>
        {activeSchema ? (
          <p className="text-gray-600 mt-1">
            Active Version: <span data-testid="schema-version">{activeSchema.version}</span>
          </p>
        ) : (
          <p className="text-gray-600 mt-1">No schema published yet. Create the first version below.</p>
        )}
      </div>

      {saveMessage && (
        <div
          className={`mb-4 p-3 rounded ${
            saveMessage.includes("success") ? "bg-green-100 text-green-800" : "bg-red-100 text-red-800"
          }`}
        >
          {saveMessage}
        </div>
      )}

      <div className="space-y-8">
        {/* Mapping Editor */}
        <div>
          <h2 className="text-xl font-semibold mb-4">Column Mapping</h2>
          <div className="border rounded p-4 space-y-4">
            {CANONICAL_FIELDS.map((field) => {
              const current = formMapping[field.key];
              return (
                <div key={field.key} className="grid grid-cols-3 gap-4 items-center">
                  <label className="font-medium">
                    {field.label}
                    {field.required && <span className="text-red-600">*</span>}
                  </label>
                  <select
                    value={current?.source || ""}
                    onChange={(e) => {
                      setMapping({ ...mapping, [field.key]: { ...current, source: e.target.value } });
                    }}
                    className="px-3 py-2 border rounded"
                  >
                    <option value="">Select column...</option>
                    {columns.map((col) => (
                      <option key={col} value={col}>
                        {col}
                      </option>
                    ))}
                  </select>
                  <div className="flex gap-2">
                    {field.format && (
                      <select
                        value={current?.format || "YYYY-MM-DD"}
                        onChange={(e) => {
                          setMapping({ ...mapping, [field.key]: { ...current, format: e.target.value } });
                        }}
                        className="px-2 py-1 border rounded text-sm"
                      >
                        {DATE_FORMATS.map((fmt) => (
                          <option key={fmt.value} value={fmt.value}>
                            {fmt.label}
                          </option>
                        ))}
                      </select>
                    )}
                    {field.currency && (
                      <label className="flex items-center gap-1 text-sm">
                        <input
                          type="checkbox"
                          checked={current?.currency || false}
                          onChange={(e) => {
                            setMapping({ ...mapping, [field.key]: { ...current, currency: e.target.checked } });
                          }}
                        />
                        Currency
                      </label>
                    )}
                    {field.default !== undefined && (
                      <input
                        type="number"
                        placeholder={`Default: ${field.default}`}
                        value={current?.default ?? ""}
                        onChange={(e) => {
                          setMapping({
                            ...mapping,
                            [field.key]: { ...current, default: e.target.value ? Number(e.target.value) : undefined },
                          });
                        }}
                        className="w-20 px-2 py-1 border rounded text-sm"
                      />
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Rules Editor */}
        <RulesEditor rules={rules} onChange={setRules} />

        {/* Version History */}
        {versionsData && versionsData.items.length > 0 && (
          <div>
            <h2 className="text-xl font-semibold mb-4">Version History</h2>
            <div className="border rounded">
              <table className="w-full">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-2 text-left">Version</th>
                    <th className="px-4 py-2 text-left">Created</th>
                    <th className="px-4 py-2 text-left">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {versionsData.items.map((v) => (
                    <tr key={v.id} className="border-t">
                      <td className="px-4 py-2">
                        {v.version}
                        {v.version === activeSchema?.version && (
                          <span className="ml-2 text-xs bg-green-100 text-green-800 px-2 py-1 rounded">
                            Active
                          </span>
                        )}
                      </td>
                      <td className="px-4 py-2 text-sm text-gray-600">
                        {new Date(v.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-2">
                        <button
                          onClick={() => {
                            setMapping(v.mapping);
                            setRules(v.rules);
                          }}
                          className="text-blue-600 hover:underline text-sm"
                        >
                          View
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Publish Button */}
        <div className="flex justify-end">
          <Button
            onClick={handlePublish}
            disabled={publishMutation.isPending}
            data-testid="schema-publish"
          >
            {publishMutation.isPending ? "Publishing..." : "Publish New Version"}
          </Button>
        </div>
      </div>
    </div>
  );
}
