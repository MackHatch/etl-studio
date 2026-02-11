import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export type RunCompareSummary = {
  id: string;
  status: string;
  schema_version: number | null;
  finished_at: string | null;
  total_rows: number | null;
  success_rows: number;
  error_rows: number;
  spend_total: number;
  clicks_total: number;
  conversions_total: number;
};

export type SpendDiff = {
  left: number;
  right: number;
  delta: number;
};

export type CampaignDiff = {
  campaign: string;
  spend_left: number;
  spend_right: number;
  delta: number;
};

export type CompareDiff = {
  total_rows: number | null;
  success_rows: number;
  error_rows: number;
  spend_total: SpendDiff;
  clicks_total: SpendDiff;
  conversions_total: SpendDiff;
  top_changed_campaigns: CampaignDiff[];
};

export type CompareResponse = {
  left_run: RunCompareSummary;
  right_run: RunCompareSummary;
  diff: CompareDiff;
};

export function useCompareRuns(
  datasetId: string,
  leftRunId: string | null,
  rightRunId: string | null
) {
  const { token } = useAuth();
  return useQuery({
    queryKey: ["compare", datasetId, leftRunId, rightRunId],
    queryFn: () => {
      if (!leftRunId || !rightRunId) {
        throw new Error("Both run IDs required");
      }
      const params = new URLSearchParams({
        leftRunId,
        rightRunId,
      });
      return apiFetch<CompareResponse>(
        `/api/datasets/${datasetId}/runs/compare?${params}`,
        {},
        token
      );
    },
    enabled: !!token && !!datasetId && !!leftRunId && !!rightRunId,
  });
}
