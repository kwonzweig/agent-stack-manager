import type { CatalogItem, Component, Kind } from "./types";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(path: string, { method = "GET", body, blob = false, signal }: {
  method?: string; body?: unknown; blob?: boolean; signal?: AbortSignal;
} = {}): Promise<T> {
  const response = await fetch(path, {
    method, signal, cache: "no-store",
    ...(body !== undefined ? { headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {}),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => null);
    throw new ApiError(error?.error || response.statusText, response.status);
  }
  return (blob ? response.blob() : response.json()) as Promise<T>;
}

export const packagePath = (id: string, suffix = "") => "/api/presets/" + encodeURIComponent(id) + suffix;
export const errorMessage = (error: unknown) => error instanceof Error ? error.message : String(error);

export function catalogMember(item: CatalogItem): Component {
  return {
    ...item, id: item.type === "component" ? item.id : "package:" + (item.packageId ?? item.id),
    name: item.name || item.title || item.id, kind: item.type === "component" ? item.kind as Kind : "package",
  };
}

export function externalUrl(value?: string | null): URL | undefined {
  try {
    const url = new URL(value || "");
    if (url.protocol === "https:" || url.protocol === "http:") return url;
  } catch {
    // Missing or invalid source URL.
  }
}

export function downloadFile(name: string, blob: Blob) {
  const url = URL.createObjectURL(blob);
  const link = Object.assign(document.createElement("a"), { href: url, download: name });
  document.body.append(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 5000);
}

export async function downloadArchive(id: string, paperclip = false) {
  const blob = await api<Blob>(packagePath(id, paperclip ? "/paperclip/export" : "/export"), { blob: true });
  downloadFile(id + (paperclip ? "-paperclip.zip" : "-apm.zip"), blob);
}
