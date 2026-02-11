"use client";

import { useState } from "react";
import { useAuth } from "@/lib/auth";
import {
  useOrg,
  useOrgMembers,
  useOrgInvites,
  useCreateInvite,
  useRevokeInvite,
  useUpdateMember,
  useRemoveMember,
  useUpdateOrg,
} from "@/features/orgs/queries";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

export default function TeamPage() {
  const { user } = useAuth();
  const activeOrgId = user?.active_org_id;
  const { data: org } = useOrg(activeOrgId || null);
  const { data: membersData } = useOrgMembers(activeOrgId || null);
  const { data: invitesData } = useOrgInvites(activeOrgId || null);
  const createInviteMutation = useCreateInvite(activeOrgId || "");
  const revokeInviteMutation = useRevokeInvite(activeOrgId || "");
  const updateMemberMutation = useUpdateMember(activeOrgId || "");
  const removeMemberMutation = useRemoveMember(activeOrgId || "");
  const updateOrgMutation = useUpdateOrg(activeOrgId || "");

  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<"OWNER" | "ADMIN" | "MEMBER">("MEMBER");
  const [orgName, setOrgName] = useState(org?.name || "");
  const [editingOrgName, setEditingOrgName] = useState(false);

  const members = membersData?.items ?? [];
  const invites = invitesData?.items ?? [];
  const canManage = user?.active_org_role === "OWNER" || user?.active_org_role === "ADMIN";
  const isOwner = user?.active_org_role === "OWNER";

  async function handleCreateInvite() {
    if (!inviteEmail.trim()) return;
    await createInviteMutation.mutateAsync({
      email: inviteEmail.trim(),
      role: inviteRole,
    });
    setInviteEmail("");
  }

  async function handleUpdateOrgName() {
    if (!orgName.trim()) return;
    await updateOrgMutation.mutateAsync({ name: orgName.trim() });
    setEditingOrgName(false);
  }

  if (!activeOrgId) {
    return (
      <div className="p-6">
        <p className="text-gray-500">No active organization.</p>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Team Settings</h1>

      {/* Organization Name */}
      <div className="mb-8 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold mb-4">Organization</h2>
        {editingOrgName && canManage ? (
          <div className="flex gap-2">
            <Input
              value={orgName}
              onChange={(e) => setOrgName(e.target.value)}
              className="flex-1"
            />
            <Button onClick={handleUpdateOrgName}>Save</Button>
            <Button variant="ghost" onClick={() => {
              setOrgName(org?.name || "");
              setEditingOrgName(false);
            }}>
              Cancel
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <span className="text-lg">{org?.name}</span>
            {canManage && (
              <Button
                variant="ghost"
                onClick={() => setEditingOrgName(true)}
                className="text-sm"
              >
                Edit
              </Button>
            )}
          </div>
        )}
      </div>

      {/* Members */}
      <div className="mb-8 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <h2 className="text-lg font-semibold mb-4">Members</h2>
        {members.length === 0 ? (
          <p className="text-sm text-gray-500">No members yet.</p>
        ) : (
          <div className="space-y-2">
            {members.map((member) => (
              <div
                key={member.id}
                className="flex items-center justify-between p-3 border rounded"
              >
                <div>
                  <div className="font-medium">{member.user_name}</div>
                  <div className="text-sm text-gray-500">{member.user_email}</div>
                </div>
                <div className="flex items-center gap-2">
                  <select
                    value={member.role}
                    onChange={(e) => {
                      if (isOwner && member.user_id !== user?.id) {
                        updateMemberMutation.mutate({
                          userId: member.user_id,
                          data: { role: e.target.value as "OWNER" | "ADMIN" | "MEMBER" },
                        });
                      }
                    }}
                    disabled={!isOwner || member.user_id === user?.id}
                    className="px-2 py-1 border rounded text-sm"
                  >
                    <option value="MEMBER">Member</option>
                    <option value="ADMIN">Admin</option>
                    <option value="OWNER">Owner</option>
                  </select>
                  {isOwner && member.user_id !== user?.id && (
                    <Button
                      variant="ghost"
                      onClick={() => {
                        if (confirm(`Remove ${member.user_name} from the organization?`)) {
                          removeMemberMutation.mutate(member.user_id);
                        }
                      }}
                      className="text-red-600 hover:text-red-800"
                    >
                      Remove
                    </Button>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Invites */}
      {canManage && (
        <div className="mb-8 rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
          <h2 className="text-lg font-semibold mb-4">Invites</h2>

          {/* Create Invite */}
          <div className="mb-4 p-3 border rounded">
            <h3 className="text-sm font-medium mb-2">Invite Member</h3>
            <div className="flex gap-2">
              <Input
                type="email"
                placeholder="email@example.com"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                className="flex-1"
                data-testid="team-invite-email"
              />
              <select
                value={inviteRole}
                onChange={(e) => setInviteRole(e.target.value as "OWNER" | "ADMIN" | "MEMBER")}
                className="px-2 py-1 border rounded"
              >
                <option value="MEMBER">Member</option>
                <option value="ADMIN">Admin</option>
                {isOwner && <option value="OWNER">Owner</option>}
              </select>
              <Button
                onClick={handleCreateInvite}
                disabled={createInviteMutation.isPending || !inviteEmail.trim()}
                data-testid="team-invite-submit"
              >
                {createInviteMutation.isPending ? "Sending..." : "Send Invite"}
              </Button>
            </div>
          </div>

          {/* Invites List */}
          {invites.length === 0 ? (
            <p className="text-sm text-gray-500">No pending invites.</p>
          ) : (
            <div className="space-y-2">
              {invites.map((invite) => (
                <div
                  key={invite.id}
                  className="flex items-center justify-between p-3 border rounded"
                >
                  <div>
                    <div className="font-medium">{invite.email}</div>
                    <div className="text-sm text-gray-500">
                      Role: {invite.role} · Expires: {new Date(invite.expires_at).toLocaleDateString()}
                    </div>
                  </div>
                  {!invite.accepted_at && (
                    <Button
                      variant="ghost"
                      onClick={() => {
                        if (confirm(`Revoke invite for ${invite.email}?`)) {
                          revokeInviteMutation.mutate(invite.id);
                        }
                      }}
                      className="text-red-600 hover:text-red-800"
                    >
                      Revoke
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
