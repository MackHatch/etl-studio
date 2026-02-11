"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

type Dataset = {
  id: string;
  name: string;
  description: string | null;
  created_at: string;
};

export default function DatasetsPage() {
  const { token } = useAuth();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [showForm, setShowForm] = useState(false);

  const { data: datasets = [], isLoading } = useQuery({
    queryKey: ["datasets"],
    queryFn: () =>
      apiFetch<Dataset[]>("/api/datasets", {}, token),
    enabled: !!token,
  });

  const createMutation = useMutation({
    mutationFn: (body: { name: string; description?: string }) =>
      apiFetch<Dataset>("/api/datasets", {
        method: "POST",
        body: JSON.stringify(body),
      }, token),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["datasets"] });
      setName("");
      setDescription("");
      setShowForm(false);
    },
  });

  function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    createMutation.mutate({ name, description: description || undefined });
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Datasets</h1>
        <Button
          data-testid="dataset-create"
          onClick={() => setShowForm(!showForm)}
        >
          New dataset
        </Button>
      </div>

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm"
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm text-gray-700">Name</label>
              <Input
                data-testid="dataset-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="Dataset name"
                required
              />
            </div>
            <div>
              <label className="mb-1 block text-sm text-gray-700">
                Description (optional)
              </label>
              <Input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Description"
              />
            </div>
          </div>
          <div className="mt-4 flex gap-2">
            <Button type="submit" data-testid="dataset-submit" disabled={createMutation.isPending}>
              {createMutation.isPending ? "Creating…" : "Create"}
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => setShowForm(false)}
            >
              Cancel
            </Button>
          </div>
          {createMutation.isError && (
            <p className="mt-2 text-sm text-red-600">
              {createMutation.error?.message}
            </p>
          )}
        </form>
      )}

      {isLoading ? (
        <p className="text-gray-500">Loading datasets…</p>
      ) : datasets.length === 0 ? (
        <p className="rounded-lg border border-dashed border-gray-300 bg-white p-8 text-center text-gray-500">
          No datasets yet. Create one to get started.
        </p>
      ) : (
        <ul className="space-y-2">
          {datasets.map((d) => (
            <li key={d.id}>
              <Link
                href={`/datasets/${d.id}`}
                className="block rounded-lg border border-gray-200 bg-white p-4 shadow-sm transition hover:border-gray-300"
              >
                <span className="font-medium">{d.name}</span>
                {d.description && (
                  <p className="mt-1 text-sm text-gray-500">{d.description}</p>
                )}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
