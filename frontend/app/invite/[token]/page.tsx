"use client";

import { useParams, useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useInvite, useAcceptInvite } from "@/features/orgs/queries";
import { Button } from "@/components/ui/Button";

export default function InviteAcceptPage() {
  const params = useParams();
  const router = useRouter();
  const token = params.token as string;
  const { token: authToken, user } = useAuth();
  const { data: invite, isLoading, error } = useInvite(token);
  const acceptMutation = useAcceptInvite();

  async function handleAccept() {
    if (!authToken) {
      router.push(`/login?redirect=/invite/${token}`);
      return;
    }
    try {
      await acceptMutation.mutateAsync(token);
      router.push("/datasets");
    } catch (e: any) {
      alert(e?.message || "Failed to accept invite");
    }
  }

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">Loading invite...</p>
      </div>
    );
  }

  if (error || !invite) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-center">
          <h1 className="text-2xl font-bold mb-2">Invite Not Found</h1>
          <p className="text-gray-500 mb-4">
            This invite may have expired or been revoked.
          </p>
          <Button onClick={() => router.push("/login")}>Go to Login</Button>
        </div>
      </div>
    );
  }

  const isExpired = new Date(invite.expires_at) < new Date();
  const isAccepted = !!invite.accepted_at;
  const emailMatches = user?.email?.toLowerCase() === invite.email.toLowerCase();

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50">
      <div className="max-w-md w-full bg-white rounded-lg border border-gray-200 shadow-sm p-6">
        <h1 className="text-2xl font-bold mb-4">Organization Invitation</h1>

        <div className="space-y-4 mb-6">
          <div>
            <div className="text-sm text-gray-500">Organization</div>
            <div className="text-lg font-medium">{invite.org_name}</div>
          </div>
          <div>
            <div className="text-sm text-gray-500">Email</div>
            <div className="text-lg">{invite.email}</div>
          </div>
          <div>
            <div className="text-sm text-gray-500">Role</div>
            <div className="text-lg">{invite.role}</div>
          </div>
        </div>

        {isExpired && (
          <div className="mb-4 p-3 bg-red-50 text-red-800 rounded text-sm">
            This invite has expired.
          </div>
        )}

        {isAccepted && (
          <div className="mb-4 p-3 bg-green-50 text-green-800 rounded text-sm">
            This invite has already been accepted.
          </div>
        )}

        {!authToken && (
          <div className="mb-4 p-3 bg-blue-50 text-blue-800 rounded text-sm">
            Please log in to accept this invite.
          </div>
        )}

        {authToken && !emailMatches && (
          <div className="mb-4 p-3 bg-yellow-50 text-yellow-800 rounded text-sm">
            You are logged in as {user?.email}, but this invite is for {invite.email}.
          </div>
        )}

        <div className="flex gap-2">
          {authToken && emailMatches && !isExpired && !isAccepted && (
            <Button
              onClick={handleAccept}
              disabled={acceptMutation.isPending}
              className="flex-1"
              data-testid="invite-accept"
            >
              {acceptMutation.isPending ? "Accepting..." : "Accept Invitation"}
            </Button>
          )}
          {!authToken && (
            <Button
              onClick={() => router.push(`/login?redirect=/invite/${token}`)}
              className="flex-1"
            >
              Log In to Accept
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
