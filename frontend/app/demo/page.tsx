"use client";

import Link from "next/link";
import { Button } from "@/components/ui/Button";

const DEMO_CREDS = [
  { email: "admin@acme.com", password: "DemoPass123!", role: "ADMIN" },
  { email: "analyst@acme.com", password: "DemoPass123!", role: "ADMIN" },
  { email: "member@acme.com", password: "DemoPass123!", role: "MEMBER" },
];

const STEPS = [
  {
    title: "Step 1: Log in",
    description: "Use one of the demo accounts to sign in.",
    href: "/login",
    linkText: "Go to Login",
  },
  {
    title: "Step 2: Create dataset",
    description: "Create a new dataset to hold your marketing CSV imports.",
    href: "/datasets",
    linkText: "Go to Datasets",
  },
  {
    title: "Step 3: Upload CSV",
    description: "Upload a CSV file. Map columns to canonical fields (date, campaign, channel, spend).",
    href: "/datasets",
    linkText: "Go to Datasets",
  },
  {
    title: "Step 4: Start import",
    description: "Configure mapping, save, and start the import. Watch real-time progress.",
    href: "/datasets",
    linkText: "Go to Datasets",
  },
  {
    title: "Step 5: View results",
    description: "See imported records, export CSV, and check validation errors.",
    href: "/datasets",
    linkText: "Go to Datasets",
  },
  {
    title: "Step 6: Analytics dashboard",
    description: "View KPIs, spend by day/channel, and anomaly detection.",
    href: "/analytics",
    linkText: "Go to Analytics",
  },
];

export default function DemoPage() {
  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="mx-auto max-w-2xl px-4">
        <div className="rounded-lg border border-gray-200 bg-white p-8 shadow-sm">
          <h1 className="text-2xl font-bold text-gray-900">2-Minute Demo</h1>
          <p className="mt-2 text-gray-600">
            Quick walkthrough of ETL Studio. Upload CSV → map columns → process → view analytics.
          </p>

          {/* Demo credentials */}
          <div className="mt-6 rounded-lg bg-blue-50 p-4">
            <h2 className="font-semibold text-blue-900">Demo login</h2>
            <p className="mt-1 text-sm text-blue-800">
              Use any of these accounts (password: <strong>DemoPass123!</strong>)
            </p>
            <div className="mt-3 space-y-2 font-mono text-sm">
              {DEMO_CREDS.map((c) => (
                <div key={c.email} className="flex items-center gap-2">
                  <span className="text-blue-700">{c.email}</span>
                  <span className="rounded bg-blue-200 px-1.5 py-0.5 text-xs text-blue-900">
                    {c.role}
                  </span>
                </div>
              ))}
            </div>
            <Link href="/login" className="mt-4 inline-block">
              <Button>Log in to start</Button>
            </Link>
          </div>

          {/* Walkthrough steps */}
          <div className="mt-8 space-y-4">
            <h2 className="font-semibold text-gray-900">Walkthrough steps</h2>
            {STEPS.map((step, i) => (
              <div
                key={step.title}
                className="flex items-start gap-4 rounded-lg border border-gray-100 p-4"
              >
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gray-200 text-sm font-medium text-gray-700">
                  {i + 1}
                </div>
                <div className="flex-1">
                  <h3 className="font-medium text-gray-900">{step.title}</h3>
                  <p className="mt-1 text-sm text-gray-600">{step.description}</p>
                  <Link href={step.href} className="mt-2 inline-block">
                    <Button variant="secondary" className="text-sm">
                      {step.linkText}
                    </Button>
                  </Link>
                </div>
              </div>
            ))}
          </div>

          {/* Quick links */}
          <div className="mt-8 flex flex-wrap gap-3 border-t border-gray-200 pt-6">
            <Link href="/login">
              <Button variant="secondary">Login</Button>
            </Link>
            <Link href="/datasets">
              <Button variant="secondary">Datasets</Button>
            </Link>
            <Link href="/analytics">
              <Button variant="secondary">Analytics</Button>
            </Link>
            <Link href="/admin/runs">
              <Button variant="secondary">Admin runs</Button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
