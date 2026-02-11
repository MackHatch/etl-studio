"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/lib/auth";
import { useOrgs, useActivateOrg } from "@/features/orgs/queries";
import { Button } from "@/components/ui/Button";

export function OrgSwitcher() {
  const { user, refreshUser } = useAuth();
  const { data: orgsData } = useOrgs();
  const activateMutation = useActivateOrg();
  const router = useRouter();
  const [open, setOpen] = useState(false);

  const orgs = orgsData?.items ?? [];
  const activeOrgId = user?.active_org_id;

  async function handleSwitch(orgId: string) {
    await activateMutation.mutateAsync(orgId);
    await refreshUser();
    setOpen(false);
    router.refresh();
  }

  if (orgs.length <= 1) {
    return null; // Don't show switcher if only one org
  }

  const activeOrg = orgs.find((o) => o.id === activeOrgId);

  return (
    <div className="relative" data-testid="org-switcher">
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-1.5 text-sm font-medium text-gray-700 hover:bg-gray-100 rounded"
      >
        <span>{activeOrg?.name || "Select org"}</span>
        <svg
          className="w-4 h-4"
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M19 9l-7 7-7-7"
          />
        </svg>
      </button>

      {open && (
        <>
          <div
            className="fixed inset-0 z-10"
            onClick={() => setOpen(false)}
          />
          <div className="absolute right-0 mt-1 w-56 bg-white border border-gray-200 rounded-lg shadow-lg z-20">
            <div className="p-2">
              <div className="px-3 py-2 text-xs font-semibold text-gray-500 uppercase">
                Organizations
              </div>
              {orgs.map((org) => (
                <button
                  key={org.id}
                  onClick={() => handleSwitch(org.id)}
                  className={`w-full text-left px-3 py-2 text-sm rounded hover:bg-gray-100 ${
                    org.id === activeOrgId ? "bg-blue-50 text-blue-700" : "text-gray-700"
                  }`}
                >
                  {org.name}
                  {org.id === activeOrgId && (
                    <span className="ml-2 text-xs text-blue-600">(active)</span>
                  )}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
