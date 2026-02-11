import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";

export type ByChannelRow = { channel: string; spend: number; clicks: number; conversions: number };
export type ByDayRow = { date: string; spend: number; clicks: number; conversions: number };
export type TopCampaignRow = { campaign: string; spend: number; clicks: number; conversions: number };

export type AnalyticsSummary = {
  range: string;
  totals: { spend: number; clicks: number; conversions: number };
  byChannel?: ByChannelRow[];
  byDay?: ByDayRow[];
  topCampaigns?: TopCampaignRow[];
  by_channel?: ByChannelRow[];
  by_day?: ByDayRow[];
  top_campaigns?: TopCampaignRow[];
};

export type AnalyticsAnomaly = {
  date: string;
  channel: string;
  spend: number;
  channel_mean: number;
  channel_std: number;
  z_score: number;
};

export type AnalyticsAnomaliesResponse = {
  range: string;
  items: AnalyticsAnomaly[];
};

export type DatasetOption = { id: string; name: string; description: string | null };

export function useDatasets(token: string | null) {
  return useQuery({
    queryKey: ["datasets"],
    queryFn: () => apiFetch<DatasetOption[]>("/api/datasets", {}, token),
    enabled: !!token,
  });
}

export function useAnalyticsSummary(
  datasetId: string | null,
  range: string,
  token: string | null
) {
  return useQuery({
    queryKey: ["analytics-summary", datasetId, range],
    queryFn: () =>
      apiFetch<AnalyticsSummary>(
        `/api/analytics/summary?datasetId=${datasetId}&range=${range}`,
        {},
        token
      ),
    enabled: !!token && !!datasetId,
  });
}

export function useAnalyticsAnomalies(
  datasetId: string | null,
  range: string,
  token: string | null
) {
  return useQuery({
    queryKey: ["analytics-anomalies", datasetId, range],
    queryFn: () =>
      apiFetch<AnalyticsAnomaliesResponse>(
        `/api/analytics/anomalies?datasetId=${datasetId}&range=${range}`,
        {},
        token
      ),
    enabled: !!token && !!datasetId,
  });
}
