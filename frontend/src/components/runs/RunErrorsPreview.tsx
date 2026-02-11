"use client";

export type RowError = {
  id: string;
  row_number: number;
  field: string | null;
  message: string;
};

const PREVIEW_LIMIT = 20;

type Props = {
  errors: RowError[];
  totalErrorCount: number;
  runId: string;
  "data-testid"?: string;
};

export function RunErrorsPreview({
  errors,
  totalErrorCount,
  runId,
  "data-testid": testId,
}: Props) {
  const preview = errors.slice(0, PREVIEW_LIMIT);
  const hasMore = totalErrorCount > PREVIEW_LIMIT;

  return (
    <div
      className="rounded-lg border border-gray-200 bg-white shadow-sm"
      data-testid={testId ?? "run-errors-preview"}
    >
      <h2 className="border-b border-gray-200 px-4 py-2 text-sm font-medium text-gray-700">
        Row errors (latest {PREVIEW_LIMIT})
        {totalErrorCount > 0 && (
          <span className="ml-2 font-normal text-gray-500">
            · {totalErrorCount} total
          </span>
        )}
      </h2>
      {preview.length === 0 ? (
        <p className="px-4 py-3 text-sm text-gray-500">
          {totalErrorCount === 0 ? "No row errors." : "Loading errors…"}
        </p>
      ) : (
        <>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead>
                <tr className="border-b border-gray-200 bg-gray-50">
                  <th className="px-4 py-2 font-medium text-gray-700">Row</th>
                  <th className="px-4 py-2 font-medium text-gray-700">Field</th>
                  <th className="px-4 py-2 font-medium text-gray-700">Message</th>
                </tr>
              </thead>
              <tbody>
                {preview.map((e) => (
                  <tr key={e.id} className="border-b border-gray-100 last:border-0">
                    <td className="px-4 py-2 font-mono">{e.row_number}</td>
                    <td className="px-4 py-2 text-gray-600">{e.field ?? "—"}</td>
                    <td className="px-4 py-2 text-red-700">{e.message}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {hasMore && (
            <div className="border-t border-gray-200 px-4 py-2 text-sm text-gray-500">
              Showing latest {PREVIEW_LIMIT} of {totalErrorCount}. Download all
              errors (CSV) in a future update.
            </div>
          )}
        </>
      )}
    </div>
  );
}
