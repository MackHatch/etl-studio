import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export interface Organization {
  id: string;
  name: string;
  created_at: string;
}

export interface OrganizationListResponse {
  items: Organization[];
}

export interface Member {
  id: string;
  org_id: string;
  user_id: string;
  role: string;
  user_email: string;
  user_name: string;
  created_at: string;
}

export interface MembersListResponse {
  items: Member[];
}

export interface Invite {
  id: string;
  org_id: string;
  email: string;
  role: string;
  expires_at: string;
  created_at: string;
  accepted_at: string | null;
}

export interface InvitesListResponse {
  items: Invite[];
}

export interface CreateOrgRequest {
  name: string;
}

export interface UpdateOrgRequest {
  name: string;
}

export interface UpdateMemberRequest {
  role: "OWNER" | "ADMIN" | "MEMBER";
}

export interface CreateInviteRequest {
  email: string;
  role: "OWNER" | "ADMIN" | "MEMBER";
}

export function useOrgs() {
  const { token } = useAuth();
  return useQuery<OrganizationListResponse>({
    queryKey: ["orgs"],
    queryFn: async () => {
      return apiFetch<OrganizationListResponse>("/api/orgs", {}, token);
    },
    enabled: !!token,
  });
}

export function useOrg(orgId: string | null) {
  const { token } = useAuth();
  return useQuery<Organization>({
    queryKey: ["org", orgId],
    queryFn: async () => {
      return apiFetch<Organization>(`/api/orgs/${orgId}`, {}, token);
    },
    enabled: !!token && !!orgId,
  });
}

export function useCreateOrg() {
  const queryClient = useQueryClient();
  const { token } = useAuth();
  return useMutation({
    mutationFn: async (data: CreateOrgRequest) => {
      return apiFetch<Organization>(
        "/api/orgs",
        { method: "POST", body: JSON.stringify(data) },
        token
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["orgs"] });
    },
  });
}

export function useUpdateOrg(orgId: string) {
  const queryClient = useQueryClient();
  const { token } = useAuth();
  return useMutation({
    mutationFn: async (data: UpdateOrgRequest) => {
      return apiFetch<Organization>(
        `/api/orgs/${orgId}`,
        { method: "PATCH", body: JSON.stringify(data) },
        token
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org", orgId] });
      queryClient.invalidateQueries({ queryKey: ["orgs"] });
    },
  });
}

export function useActivateOrg() {
  const queryClient = useQueryClient();
  const { token } = useAuth();
  return useMutation({
    mutationFn: async (orgId: string) => {
      return apiFetch(`/api/orgs/${orgId}/activate`, { method: "POST" }, token);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
    },
  });
}

export function useOrgMembers(orgId: string | null) {
  const { token } = useAuth();
  return useQuery<MembersListResponse>({
    queryKey: ["org", orgId, "members"],
    queryFn: async () => {
      return apiFetch<MembersListResponse>(`/api/orgs/${orgId}/members`, {}, token);
    },
    enabled: !!token && !!orgId,
  });
}

export function useUpdateMember(orgId: string) {
  const queryClient = useQueryClient();
  const { token } = useAuth();
  return useMutation({
    mutationFn: async ({ userId, data }: { userId: string; data: UpdateMemberRequest }) => {
      return apiFetch(
        `/api/orgs/${orgId}/members/${userId}`,
        { method: "PATCH", body: JSON.stringify(data) },
        token
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org", orgId, "members"] });
    },
  });
}

export function useRemoveMember(orgId: string) {
  const queryClient = useQueryClient();
  const { token } = useAuth();
  return useMutation({
    mutationFn: async (userId: string) => {
      return apiFetch(`/api/orgs/${orgId}/members/${userId}`, { method: "DELETE" }, token);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org", orgId, "members"] });
    },
  });
}

export function useOrgInvites(orgId: string | null) {
  const { token } = useAuth();
  return useQuery<InvitesListResponse>({
    queryKey: ["org", orgId, "invites"],
    queryFn: async () => {
      return apiFetch<InvitesListResponse>(`/api/orgs/${orgId}/invites`, {}, token);
    },
    enabled: !!token && !!orgId,
  });
}

export function useCreateInvite(orgId: string) {
  const queryClient = useQueryClient();
  const { token } = useAuth();
  return useMutation({
    mutationFn: async (data: CreateInviteRequest) => {
      return apiFetch(
        `/api/orgs/${orgId}/invites`,
        { method: "POST", body: JSON.stringify(data) },
        token
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org", orgId, "invites"] });
    },
  });
}

export function useRevokeInvite(orgId: string) {
  const queryClient = useQueryClient();
  const { token } = useAuth();
  return useMutation({
    mutationFn: async (inviteId: string) => {
      return apiFetch(`/api/orgs/${orgId}/invites/${inviteId}`, { method: "DELETE" }, token);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org", orgId, "invites"] });
    },
  });
}

export interface InviteDetail {
  id: string;
  org_id: string;
  org_name: string;
  email: string;
  role: string;
  expires_at: string;
  created_at: string;
  accepted_at: string | null;
}

export function useInvite(token: string | null) {
  return useQuery<InviteDetail>({
    queryKey: ["invite", token],
    queryFn: async () => {
      return apiFetch<InviteDetail>(`/api/invites/${token}`, {}, null); // Public endpoint
    },
    enabled: !!token,
  });
}

export function useAcceptInvite() {
  const queryClient = useQueryClient();
  const { token } = useAuth();
  return useMutation({
    mutationFn: async (inviteToken: string) => {
      return apiFetch(`/api/invites/${inviteToken}/accept`, { method: "POST" }, token);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["auth", "me"] });
      queryClient.invalidateQueries({ queryKey: ["orgs"] });
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
    },
  });
}
