#!/usr/bin/env python3
"""
Smoke test: login -> create dataset -> upload CSV -> set mapping -> start run ->
poll until SUCCEEDED -> fetch records -> download records.csv.
Run against a running backend (and worker) with postgres/redis.
"""
import os
import sys
import time
from pathlib import Path

import httpx

BASE_URL = os.environ.get("SMOKE_BASE_URL", "http://localhost:8000")
API = f"{BASE_URL}/api"
TIMEOUT = int(os.environ.get("SMOKE_TIMEOUT", "60"))
POLL_INTERVAL = 1.0


def main() -> int:
    fixture_path = Path(__file__).resolve().parent.parent / "fixtures" / "sample.csv"
    if not fixture_path.exists():
        print(f"Fixture not found: {fixture_path}", file=sys.stderr)
        return 1

    email = "admin@example.com"
    password = "adminpassword"

    with httpx.Client(base_url=API, timeout=30.0) as client:
        # Login
        r = client.post("/auth/login", json={"email": email, "password": password})
        r.raise_for_status()
        data = r.json()
        token = data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create dataset
        r = client.post("/datasets", json={"name": "smoke-dataset", "description": "CI smoke"}, headers=headers)
        r.raise_for_status()
        dataset = r.json()
        dataset_id = dataset["id"]

        # Upload CSV
        with open(fixture_path, "rb") as f:
            r = client.post(
                f"/datasets/{dataset_id}/uploads",
                files={"file": ("sample.csv", f, "text/csv")},
                headers=headers,
            )
        r.raise_for_status()
        run = r.json()
        run_id = run["id"]
        assert run["status"] == "DRAFT", f"Expected DRAFT, got {run['status']}"

        # Set mapping (required before start)
        mapping = {
            "date": {"source": "date", "format": "YYYY-MM-DD"},
            "campaign": {"source": "campaign"},
            "channel": {"source": "channel"},
            "spend": {"source": "spend", "currency": True},
            "clicks": {"source": "clicks", "default": 0},
            "conversions": {"source": "conversions", "default": 0},
        }
        r = client.put(f"/datasets/{dataset_id}/mapping", json={"mapping": mapping}, headers=headers)
        r.raise_for_status()

        # Start run
        r = client.post(f"/runs/{run_id}/start", headers=headers)
        r.raise_for_status()

        # Poll until SUCCEEDED or FAILED
        deadline = time.monotonic() + TIMEOUT
        while time.monotonic() < deadline:
            r = client.get(f"/runs/{run_id}", headers=headers)
            r.raise_for_status()
            run = r.json()
            status = run["status"]
            if status == "SUCCEEDED":
                break
            if status == "FAILED":
                print(f"Run failed: {run.get('error_summary', 'unknown')}", file=sys.stderr)
                return 1
            time.sleep(POLL_INTERVAL)
        else:
            print("Run did not complete within timeout", file=sys.stderr)
            return 1

        # Fetch records
        r = client.get(f"/runs/{run_id}/records", params={"page": 1, "pageSize": 5}, headers=headers)
        r.raise_for_status()
        records_data = r.json()
        items = records_data.get("items", [])
        if not items:
            print("Expected at least one record", file=sys.stderr)
            return 1

        # Download records.csv and check header
        r = client.get(f"/runs/{run_id}/records.csv", headers=headers)
        r.raise_for_status()
        text = r.text
        lines = text.strip().split("\n")
        if not lines:
            print("records.csv is empty", file=sys.stderr)
            return 1
        header = lines[0].lower()
        for col in ["row_number", "date", "campaign", "channel", "spend", "clicks", "conversions"]:
            if col not in header:
                print(f"Expected column '{col}' in records.csv header: {lines[0]}", file=sys.stderr)
                return 1

    print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
