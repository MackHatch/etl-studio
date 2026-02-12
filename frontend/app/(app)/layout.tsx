"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/Button";
import { DemoWalkthrough } from "@/components/demo/DemoWalkthrough";
import { OrgSwitcher } from "@/components/org/OrgSwitcher";

export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { ready, token, user, logout, refreshUser } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    if (!ready) return;
    if (!token) {
      const redirect = encodeURIComponent(pathname || "/datasets");
      router.replace(`/login?redirect=${redirect}`);
    } else if (token && !user?.active_org_id) {
      // Refresh user to get active org
      refreshUser();
    }
  }, [ready, token, pathname, router, user?.active_org_id, refreshUser]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-gray-500">Loading…</p>
      </div>
    );
  }

  if (!token) {
    return null;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <nav className="border-b border-gray-200 bg-white">
        <div className="mx-auto flex h-14 max-w-6xl items-center justify-between px-4">
          <div className="flex items-center gap-6">
            <Link
              href="/datasets"
              className="text-sm font-medium text-gray-700 hover:text-gray-900"
              data-testid="nav-datasets"
            >
              Datasets
            </Link>
            <Link
              href="/analytics"
              className="text-sm font-medium text-gray-700 hover:text-gray-900"
              data-testid="nav-analytics"
            >
              Analytics
            </Link>
            <Link
              href="/team"
              className="text-sm font-medium text-gray-700 hover:text-gray-900"
            >
              Team
            </Link>
            <Link
              href="/demo"
              className="text-sm font-medium text-gray-700 hover:text-gray-900"
            >
              Demo
            </Link>
            {user?.role === "ADMIN" && (
              <Link
                href="/admin/runs"
                className="text-sm font-medium text-gray-700 hover:text-gray-900"
                data-testid="nav-admin-runs"
              >
                Admin Runs
              </Link>
            )}
          </div>
          <div className="flex items-center gap-4">
            <OrgSwitcher />
            <span className="text-sm text-gray-600">{user?.email}</span>
            <Button variant="ghost" onClick={() => logout()}>
              Sign out
            </Button>
          </div>
        </div>
      </nav>
      <main className="mx-auto max-w-6xl px-4 py-8">
        {process.env.NODE_ENV === "development" && <DemoWalkthrough />}
        {children}
      </main>
    </div>
  );
}
