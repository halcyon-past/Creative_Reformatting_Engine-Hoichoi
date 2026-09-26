import type {
  Asset,
  ComplianceReport,
  Job,
  ReframePoint,
  SpecSheet,
  Variant,
} from "./types";

const BASE = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: init?.body instanceof FormData ? {} : { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      detail = body?.error?.message ?? body?.detail ?? detail;
    } catch {
      /* the body was not JSON; the status line is the best we have */
    }
    throw new Error(detail);
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const api = {
  spec: () => request<SpecSheet>("/spec"),

  listAssets: () => request<Asset[]>("/assets"),
  getAsset: (id: string) => request<Asset>(`/assets/${id}`),
  deleteAsset: (id: string) => request<void>(`/assets/${id}`, { method: "DELETE" }),

  upload: (file: File, title?: string) => {
    const form = new FormData();
    form.append("file", file);
    if (title) form.append("title", title);
    form.append("auto_reformat", "true");
    return request<{ asset: Asset; job: Job | null }>("/assets", {
      method: "POST",
      body: form,
    });
  },

  reformat: (id: string) => request<Job>(`/assets/${id}/reformat`, { method: "POST" }),

  regenerate: (id: string, profileId: string) =>
    request<Job>(`/assets/${id}/variants/regenerate`, {
      method: "POST",
      body: JSON.stringify({ profile_id: profileId }),
    }),

  listVariants: (id: string) => request<Variant[]>(`/assets/${id}/variants`),
  library: (id: string) => request<Variant[]>(`/assets/${id}/library`),
  getVariant: (id: string) => request<Variant>(`/variants/${id}`),

  report: (id: string) =>
    request<{
      variant_id: string;
      profile_id: string;
      status: string;
      summary: Record<string, number>;
      report: ComplianceReport;
    }>(`/variants/${id}/report`),

  reframePath: (id: string) =>
    request<{ variant_id: string; points: ReframePoint[]; source_size: [number, number] }>(
      `/variants/${id}/reframe-path`,
    ),

  revalidate: (id: string) => request<Job>(`/variants/${id}/revalidate`, { method: "POST" }),

  getJob: (id: string) => request<Job>(`/jobs/${id}`),
  listJobs: (assetId?: string) =>
    request<Job[]>(`/jobs${assetId ? `?asset_id=${assetId}` : ""}`),
};
