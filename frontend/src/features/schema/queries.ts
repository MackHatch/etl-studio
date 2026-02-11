import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export interface SchemaVersion {
  id: string;
  dataset_id: string;
  version: number;
  mapping: Record<string, any>;
  rules: Record<string, any>;
  created_by_user_id: string | null;
  created_at: string;
}

export interface ActiveSchema {
  version: number;
  mapping: Record<string, any>;
  rules: Record<string, any>;
}

export interface SchemaVersionsResponse {
  items: SchemaVersion[];
}

export interface PublishSchemaRequest {
  mapping: Record<string, any>;
  rules: Record<string, any>;
}

export function useActiveSchema(datasetId: string) {
  const { token } = useAuth();
  return useQuery<ActiveSchema>({
    queryKey: ["schema", "active", datasetId],
    queryFn: async () => {
      return apiFetch<ActiveSchema>(`/api/datasets/${datasetId}/schema/active`, {}, token);
    },
    enabled: !!token && !!datasetId,
  });
}

export function useSchemaVersions(datasetId: string) {
  const { token } = useAuth();
  return useQuery<SchemaVersionsResponse>({
    queryKey: ["schema", "versions", datasetId],
    queryFn: async () => {
      return apiFetch<SchemaVersionsResponse>(`/api/datasets/${datasetId}/schema/versions`, {}, token);
    },
    enabled: !!token && !!datasetId,
  });
}

export function usePublishSchema(datasetId: string) {
  const queryClient = useQueryClient();
  const { token } = useAuth();
  return useMutation({
    mutationFn: async (data: PublishSchemaRequest) => {
      return apiFetch(
        `/api/datasets/${datasetId}/schema/publish`,
        { method: "POST", body: JSON.stringify(data) },
        token
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["schema", datasetId] });
      queryClient.invalidateQueries({ queryKey: ["datasets", datasetId] });
    },
  });
}

export function useRerun(runId: string) {
  const queryClient = useQueryClient();
  const { token } = useAuth();
  return useMutation({
    mutationFn: async (data: { schema_version?: number }) => {
      return apiFetch(
        `/api/runs/${runId}/rerun`,
        { method: "POST", body: JSON.stringify(data) },
        token
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["runs"] });
    },
  });
}
