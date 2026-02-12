"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/Button";
import { baseURL } from "@/lib/api";

type DemoMetadata = {
  dataset_id: string;
  run_a_id: string;
  run_b_id: string;
  org_name: string;
  dataset_name: string;
};

const DEMO_EMAIL = "demo@etl.com";
const DEMO_PASSWORD = "DemoPass123!";

export default function DemoPage() {
  const [metadata, setMetadata] = useState<DemoMetadata | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  useEffect(() => {
    fetch(`${baseURL}/api/demo`)
      .then((r) => r.json())
      .then((data) => data && data.dataset_id && setMetadata(data))
      .catch(() => {});
  }, []);

  const copyToClipboard = async (text: string, id: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(id);
      setTimeout(() => setCopied(null), 2000);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand("copy");
      document.body.removeChild(ta);
      setCopied(id);
      setTimeout(() => setCopied(null), 2000);
    }
  };

  const downloadSample = () => {
    const link = document.createElement("a");
    link.href = "/sample.csv";
    link.download = "sample.csv";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  // Curl templates (user fills token/dataset/run)
  const curlLogin = `curl -X POST ${baseURL}/api/auth/login \\
  -H "Content-Type: application/json" \\
  -d '{"email":"${DEMO_EMAIL}","password":"${DEMO_PASSWORD}"}'`;
  const curlUpload = metadata
    ? `curl -X POST ${baseURL}/api/datasets/${metadata.dataset_id}/uploads \\
  -H "Authorization: Bearer YOUR_TOKEN" \\
  -F "file=@sample.csv"`
    : "(Log in first, then get dataset ID from /datasets)";
  const curlStart = metadata
    ? `curl -X POST ${baseURL}/api/runs/RUN_ID/start \\
  -H "Authorization: Bearer YOUR_TOKEN"`
    : "(Get run ID from dataset page after upload)";
  const curlExport = metadata
    ? `curl -X GET ${baseURL}/api/runs/RUN_ID/records.csv \\
  -H "Authorization: Bearer YOUR_TOKEN" -o records.csv`
    : "(Get run ID from dataset page)";

  return (
    <div className="min-h-screen bg-gray-50 py-12">
      <div className="mx-auto max-w-2xl px-4">
        <div className="rounded-lg border border-gray-200 bg-white p-8 shadow-sm">
          <h1 className="text-2xl font-bold text-gray-900">2-Minute Demo</h1>
          <p className="mt-2 text-gray-600">
            Upload CSV → map columns → start run → watch SSE progress → view results → compare runs.
          </p>

          {/* Demo credentials */}
          <div className="mt-6 rounded-lg bg-blue-50 p-4">
            <h2 className="font-semibold text-blue-900">Demo login</h2>
            <p className="mt-1 text-sm text-blue-800">
              <strong>{DEMO_EMAIL}</strong> / <strong>{DEMO_PASSWORD}</strong>
            </p>
            <Link href="/login" className="mt-4 inline-block">
              <Button>Log in to start</Button>
            </Link>
          </div>

          {/* Quick actions */}
          <div className="mt-8 space-y-4">
            <h2 className="font-semibold text-gray-900">Quick actions</h2>

            <div className="rounded-lg border border-gray-100 p-4">
              <h3 className="font-medium text-gray-900">Upload sample.csv</h3>
              <p className="mt-1 text-sm text-gray-600">
                Download the sample CSV, then upload it to the demo dataset.
              </p>
              <div className="mt-2 flex gap-2">
                <Button variant="secondary" onClick={downloadSample}>
                  Download sample.csv
                </Button>
                {metadata && (
                  <Link href={`/datasets/${metadata.dataset_id}`}>
                    <Button variant="secondary">Go to dataset →</Button>
                  </Link>
                )}
              </div>
            </div>

            <div className="rounded-lg border border-gray-100 p-4">
              <h3 className="font-medium text-gray-900">View running job (SSE)</h3>
              <p className="mt-1 text-sm text-gray-600">
                Watch real-time progress for a run.
              </p>
              {metadata && (
                <div className="mt-2 flex gap-2">
                  <Link href={`/runs/${metadata.run_a_id}`}>
                    <Button variant="secondary">Run A (schema v1)</Button>
                  </Link>
                  <Link href={`/runs/${metadata.run_b_id}`}>
                    <Button variant="secondary">Run B (schema v2)</Button>
                  </Link>
                </div>
              )}
            </div>

            <div className="rounded-lg border border-gray-100 p-4">
              <h3 className="font-medium text-gray-900">View results + export</h3>
              <p className="mt-1 text-sm text-gray-600">
                See imported records and export as CSV.
              </p>
              {metadata && (
                <div className="mt-2 flex gap-2">
                  <Link href={`/runs/${metadata.run_a_id}/results`}>
                    <Button variant="secondary">Run A results</Button>
                  </Link>
                  <Link href={`/runs/${metadata.run_b_id}/results`}>
                    <Button variant="secondary">Run B results</Button>
                  </Link>
                </div>
              )}
            </div>

            <div className="rounded-lg border border-gray-100 p-4">
              <h3 className="font-medium text-gray-900">Compare runs</h3>
              <p className="mt-1 text-sm text-gray-600">
                Compare Run A (clean) vs Run B (with errors) — see schema impact.
              </p>
              {metadata && (
                <Link
                  href={`/datasets/${metadata.dataset_id}/compare?leftRunId=${metadata.run_a_id}&rightRunId=${metadata.run_b_id}`}
                  className="mt-2 inline-block"
                >
                  <Button variant="secondary">Compare Run A vs Run B</Button>
                </Link>
              )}
            </div>

            <div className="rounded-lg border border-gray-100 p-4">
              <h3 className="font-medium text-gray-900">Team (invite / members)</h3>
              <Link href="/team" className="mt-2 inline-block">
                <Button variant="secondary">Go to Team</Button>
              </Link>
            </div>
          </div>

          {/* Copy curl */}
          <div className="mt-8 rounded-lg border border-gray-200 bg-gray-50 p-4">
            <h2 className="font-semibold text-gray-900">Copy curl</h2>
            <div className="mt-3 space-y-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm">Login</span>
                <Button variant="secondary" className="text-xs" onClick={() => copyToClipboard(curlLogin, "login")}>
                  {copied === "login" ? "Copied!" : "Copy"}
                </Button>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm">Upload</span>
                <Button variant="secondary" className="text-xs" onClick={() => copyToClipboard(curlUpload, "upload")}>
                  {copied === "upload" ? "Copied!" : "Copy"}
                </Button>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm">Start run</span>
                <Button variant="secondary" className="text-xs" onClick={() => copyToClipboard(curlStart, "start")}>
                  {copied === "start" ? "Copied!" : "Copy"}
                </Button>
              </div>
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm">Export records</span>
                <Button variant="secondary" className="text-xs" onClick={() => copyToClipboard(curlExport, "export")}>
                  {copied === "export" ? "Copied!" : "Copy"}
                </Button>
              </div>
            </div>
          </div>

          {/* External links */}
          <div className="mt-8 flex flex-wrap gap-3 border-t border-gray-200 pt-6">
            <a href="http://localhost:5555" target="_blank" rel="noopener noreferrer">
              <Button variant="secondary">Open Flower</Button>
            </a>
            <a href="http://localhost:16686" target="_blank" rel="noopener noreferrer">
              <Button variant="secondary">Open Jaeger</Button>
            </a>
            <a href="http://localhost:9001" target="_blank" rel="noopener noreferrer">
              <Button variant="secondary">Open MinIO</Button>
            </a>
            <Link href="/login">
              <Button variant="secondary">Login</Button>
            </Link>
            <Link href="/datasets">
              <Button variant="secondary">Datasets</Button>
            </Link>
            <Link href="/analytics">
              <Button variant="secondary">Analytics</Button>
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
}
