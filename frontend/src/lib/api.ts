export const base = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8000";
const apiKey = process.env.NEXT_PUBLIC_API_KEY || "changeme-local-dev";

export async function api<T = any>(path: string, method = "GET", body?: any): Promise<T> {
  const isForm = body instanceof FormData;
  const headers: Record<string, string> = { "X-API-Key": apiKey };
  if (!isForm) headers["Content-Type"] = "application/json";
  const res = await fetch(`${base}${path}`, {
    method,
    headers,
    body: body ? (isForm ? body : JSON.stringify(body)) : undefined,
  });
  if (!res.ok) throw new Error(await res.text());
  const text = await res.text();
  return text ? JSON.parse(text) : (undefined as T);
}

// Trigger a browser download for an authenticated export endpoint.
export async function download(path: string, filename: string) {
  const res = await fetch(`${base}${path}`, { headers: { "X-API-Key": apiKey } });
  if (!res.ok) throw new Error(await res.text());
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
