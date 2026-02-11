const baseURL =
  typeof window !== "undefined"
    ? (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000")
    : process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export type ApiError = {
  error: { code: string; message: string; details?: Record<string, unknown> };
};

export async function apiFetch<T = unknown>(
  path: string,
  init: RequestInit = {},
  token?: string | null
): Promise<T> {
  const url = path.startsWith("http") ? path : `${baseURL}${path}`;
  const headers = new Headers(init.headers);
  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }
  if (!headers.has("Content-Type") && init.body && typeof init.body === "string") {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(url, { ...init, headers });
  const text = await res.text();
  if (!res.ok) {
    let payload: ApiError;
    try {
      payload = JSON.parse(text) as ApiError;
    } catch {
      payload = {
        error: { code: "unknown", message: res.statusText || "Request failed" },
      };
    }
    if (payload?.error) {
      throw new Error(payload.error.message || payload.error.code);
    }
    throw new Error(text || res.statusText);
  }
  if (!text) return undefined as T;
  try {
    return JSON.parse(text) as T;
  } catch {
    return text as T;
  }
}

export { baseURL };
