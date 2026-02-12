"use client";

import Link from "next/link";
import { useState } from "react";
import { Button } from "@/components/ui/Button";
import { baseURL } from "@/lib/api";

const DEMO_EMAIL = "demo@etl.com";
const DEMO_PASSWORD = "DemoPass123!";

export function DemoWalkthrough() {
  const [dismissed, setDismissed] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  if (dismissed) return null;

  const apiUrl = baseURL;

  const copyToClipboard = async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(id);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      // Fallback for older browsers
      const textarea = document.createElement("textarea");
      textarea.value = text;
      document.body.appendChild(textarea);
      textarea.select();
      document.execCommand("copy");
      document.body.removeChild(textarea);
      setCopied(id);
      setTimeout(() => setCopied(null), 2000);
    }
  };

  const curlLogin = `curl -X POST ${apiUrl}/api/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"email":"${DEMO_EMAIL}","password":"${DEMO_PASSWORD}"}'`;

  const curlCreateDataset = `curl -X POST ${apiUrl}/api/datasets \\
  -H "Content-Type: application/json" \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -d '{"name":"My Dataset","description":"Description"}'`;

  const curlUpload = `curl -X POST ${apiUrl}/api/datasets/DATASET_ID/uploads \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -F "file=@sample.csv"`;

  const downloadSample = () => {
    const link = document.createElement("a");
    link.href = "/sample.csv";
    link.download = "sample.csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  return (
    <div
      className="mb-6 rounded-lg border-2 border-blue-200 bg-blue-50 p-4 shadow-sm"
      data-testid="demo-walkthrough"
    >
      <div className="mb-3 flex items-start justify-between">
        <div>
          <h2 className="text-lg font-semibold text-blue-900">Demo Walkthrough</h2>
          <p className="mt-1 text-sm text-blue-700">
            Quick guide to explore ETL Studio. Demo credentials: <strong>{DEMO_EMAIL}</strong> /{" "}
            <strong>{DEMO_PASSWORD}</strong>. <Link href="/demo" className="underline">Full 2-min guide →</Link>
          </p>
        </div>
        <button
          onClick={() => setDismissed(true)}
          className="text-blue-600 hover:text-blue-800"
          aria-label="Dismiss"
        >
          ×
        </button>
      </div>

      <div className="mt-4 space-y-3 text-sm">
        <div className="flex items-center gap-2">
          <span className="font-medium text-blue-900">1.</span>
          <span className="text-blue-800">Create dataset</span>
          <Button
            className="px-2 py-1 text-xs"
            variant="secondary"
            onClick={() => copyToClipboard(curlCreateDataset, "create-dataset")}
            data-testid="demo-copy-curl"
          >
            {copied === "create-dataset" ? "Copied!" : "Copy curl"}
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-medium text-blue-900">2.</span>
          <span className="text-blue-800">Upload sample CSV</span>
          <Button className="px-2 py-1 text-xs" variant="secondary" onClick={downloadSample}>
            Download sample.csv
          </Button>
          <Button
            className="px-2 py-1 text-xs"
            variant="secondary"
            onClick={() => copyToClipboard(curlUpload, "upload")}
            data-testid="demo-copy-curl"
          >
            {copied === "upload" ? "Copied!" : "Copy curl"}
          </Button>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-medium text-blue-900">3.</span>
          <span className="text-blue-800">Configure mapping (map columns to canonical fields)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-medium text-blue-900">4.</span>
          <span className="text-blue-800">Start run (processes CSV with mapping)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-medium text-blue-900">5.</span>
          <span className="text-blue-800">Watch SSE progress (real-time updates)</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-medium text-blue-900">6.</span>
          <span className="text-blue-800">View results table + export CSV</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-medium text-blue-900">7.</span>
          <span className="text-blue-800">View analytics dashboard</span>
        </div>
      </div>

      <div className="mt-4 flex gap-2">
        <Button
          className="px-2 py-1 text-xs"
          variant="secondary"
          onClick={() => copyToClipboard(curlLogin, "login")}
          data-testid="demo-copy-curl"
        >
          {copied === "login" ? "Copied!" : "Copy curl: login"}
        </Button>
      </div>
    </div>
  );
}
