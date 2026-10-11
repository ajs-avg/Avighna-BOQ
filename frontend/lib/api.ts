import { clearSession, getToken, redirectToLogin } from "./auth";
import type {
  AIStatus,
  AuditListResponse,
  CreateJobResponse,
  FitoutItem,
  HealthResponse,
  InviteRequest,
  InviteResponse,
  JobListResponse,
  JobRecord,
  JobStatus,
  LoginRequest,
  MeasurementExtraction,
  MemberSpec,
  Module,
  RejectRequest,
  RoleUpdate,
  SetPasswordRequest,
  SheetRecord,
  Standards,
  SystemInfo,
  TokenResponse,
  UserProfile,
} from "./types";

/** Base URL of the FastAPI backend (no trailing slash). */
export const API_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(/\/+$/, "");

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export function isApiError(err: unknown): err is ApiError {
  return err instanceof ApiError;
}

interface ApiFetchOptions extends Omit<RequestInit, "body"> {
  /** JSON-serialisable body (objects) or a FormData / Blob / string passed through as-is. */
  body?: unknown;
  /** Skip the automatic redirect-to-login on 401 (used by the login form itself). */
  noAuthRedirect?: boolean;
}

async function readDetail(res: Response): Promise<string> {
  const fallback = res.statusText || `HTTP ${res.status}`;
  try {
    const text = await res.text();
    if (!text) return fallback;
    try {
      const parsed: unknown = JSON.parse(text);
      if (parsed && typeof parsed === "object" && "detail" in parsed) {
        const detail = (parsed as { detail: unknown }).detail;
        if (typeof detail === "string") return detail;
        if (Array.isArray(detail)) {
          // FastAPI validation errors: [{loc, msg, type}]
          const msgs = detail
            .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : ""))
            .filter(Boolean);
          if (msgs.length) return msgs.join("; ");
        }
        return JSON.stringify(detail);
      }
      return text;
    } catch {
      return text.slice(0, 300);
    }
  } catch {
    return fallback;
  }
}

function buildHeaders(init: ApiFetchOptions, isJsonBody: boolean): Headers {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token && !headers.has("Authorization")) headers.set("Authorization", `Bearer ${token}`);
  if (isJsonBody && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  return headers;
}

/** Low-level fetch returning the raw Response (bearer attached, errors thrown as ApiError). */
export async function apiRequest(path: string, init: ApiFetchOptions = {}): Promise<Response> {
  const { body, noAuthRedirect, ...rest } = init;
  const isPassthrough =
    body === undefined ||
    body === null ||
    typeof body === "string" ||
    (typeof FormData !== "undefined" && body instanceof FormData) ||
    (typeof Blob !== "undefined" && body instanceof Blob);
  const headers = buildHeaders(init, !isPassthrough);

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, {
      ...rest,
      headers,
      body: isPassthrough ? (body as BodyInit | null | undefined) : JSON.stringify(body),
      cache: "no-store",
    });
  } catch {
    throw new ApiError(0, `Cannot reach the API at ${API_URL}. Is the backend running?`);
  }

  if (res.status === 401 && !noAuthRedirect) {
    clearSession();
    redirectToLogin();
    throw new ApiError(401, "Your session has expired. Please sign in again.");
  }
  if (!res.ok) {
    throw new ApiError(res.status, await readDetail(res));
  }
  return res;
}

/** Typed JSON fetch. 204 / empty bodies resolve to `undefined as T`. */
export async function apiFetch<T>(path: string, init: ApiFetchOptions = {}): Promise<T> {
  const res = await apiRequest(path, init);
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  if (!text) return undefined as T;
  return JSON.parse(text) as T;
}

// ---- health / auth ---------------------------------------------------------

export const getHealth = () => apiFetch<HealthResponse>("/healthz", { noAuthRedirect: true });

export const login = (body: LoginRequest) =>
  apiFetch<TokenResponse>("/api/v1/auth/login", { method: "POST", body, noAuthRedirect: true });

export const setPassword = (body: SetPasswordRequest) =>
  apiFetch<UserProfile>("/api/v1/auth/set-password", { method: "POST", body });

export const getMe = (opts?: { noAuthRedirect?: boolean }) =>
  apiFetch<UserProfile>("/api/v1/me", { noAuthRedirect: opts?.noAuthRedirect });

export const getAIStatus = () => apiFetch<AIStatus>("/api/v1/ai/status");

export const getSystem = () => apiFetch<SystemInfo>("/api/v1/system");

/** A downloaded file: the bytes plus the server-suggested file name. */
export interface BlobDownload {
  blob: Blob;
  filename: string;
}

/** Read the file name out of a `Content-Disposition` header (RFC 6266 / 5987), else `fallback`. */
export function filenameFromDisposition(res: Response, fallback: string): string {
  const header = res.headers.get("Content-Disposition");
  if (!header) return fallback;
  const utf8 = /filename\*\s*=\s*(?:UTF-8|utf-8)''([^;]+)/.exec(header);
  if (utf8?.[1]) {
    try {
      return decodeURIComponent(utf8[1].trim()) || fallback;
    } catch {
      /* fall through to the plain form */
    }
  }
  const plain = /filename\s*=\s*"?([^";]+)"?/.exec(header);
  const name = plain?.[1]?.trim();
  return name || fallback;
}

// ---- jobs ------------------------------------------------------------------

export interface ListJobsParams {
  limit?: number;
  offset?: number;
  module?: Module | "";
  status?: JobStatus | "";
}

export function listJobs(params: ListJobsParams = {}) {
  const q = new URLSearchParams();
  if (params.limit !== undefined) q.set("limit", String(params.limit));
  if (params.offset !== undefined) q.set("offset", String(params.offset));
  if (params.module) q.set("module", params.module);
  if (params.status) q.set("status", params.status);
  const qs = q.toString();
  return apiFetch<JobListResponse>(`/api/v1/jobs${qs ? `?${qs}` : ""}`);
}

export const getJob = (id: string) => apiFetch<JobRecord>(`/api/v1/jobs/${encodeURIComponent(id)}`);

export const deleteJob = (id: string) =>
  apiFetch<void>(`/api/v1/jobs/${encodeURIComponent(id)}`, { method: "DELETE" });

/**
 * Multipart upload with progress (XMLHttpRequest so we get upload events).
 * Resolves with `{job_id, status}`; rejects with ApiError.
 */
export function createJob(
  formData: FormData,
  onProgress?: (fraction: number) => void,
  signal?: AbortSignal,
): Promise<CreateJobResponse> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `${API_URL}/api/v1/jobs`);
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.setRequestHeader("Accept", "application/json");

    xhr.upload.onprogress = (e) => {
      if (onProgress && e.lengthComputable && e.total > 0) onProgress(e.loaded / e.total);
    };
    xhr.onerror = () => reject(new ApiError(0, `Cannot reach the API at ${API_URL}. Is the backend running?`));
    xhr.onabort = () => reject(new ApiError(0, "Upload cancelled"));
    xhr.onload = () => {
      const status = xhr.status;
      if (status === 401) {
        clearSession();
        redirectToLogin();
        reject(new ApiError(401, "Your session has expired. Please sign in again."));
        return;
      }
      if (status >= 200 && status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as CreateJobResponse);
        } catch {
          reject(new ApiError(status, "Unexpected response from the server"));
        }
        return;
      }
      let detail = xhr.statusText || `HTTP ${status}`;
      try {
        const parsed: unknown = JSON.parse(xhr.responseText);
        if (parsed && typeof parsed === "object" && "detail" in parsed) {
          const d = (parsed as { detail: unknown }).detail;
          detail = typeof d === "string" ? d : JSON.stringify(d);
        }
      } catch {
        if (xhr.responseText) detail = xhr.responseText.slice(0, 300);
      }
      reject(new ApiError(status, detail));
    };

    if (signal) {
      if (signal.aborted) {
        reject(new ApiError(0, "Upload cancelled"));
        return;
      }
      signal.addEventListener("abort", () => xhr.abort(), { once: true });
    }
    xhr.send(formData);
  });
}

export const getSheets = (jobId: string) =>
  apiFetch<SheetRecord[]>(`/api/v1/jobs/${encodeURIComponent(jobId)}/sheets`);

/** `thumb` is the ~1600 px render; `full` is the high-resolution render when it exists (the API falls back to the thumb otherwise). */
export type PreviewSize = "thumb" | "full";

/**
 * Fetch a sheet preview PNG with the bearer token and return an object URL (caller revokes).
 * `size` defaults to the thumb so existing callers are unchanged; the lightbox asks for `full`.
 */
export async function getPreviewBlobUrl(jobId: string, sheetId: string, size: PreviewSize = "thumb"): Promise<string> {
  const query = size === "full" ? "?size=full" : "";
  const res = await apiRequest(
    `/api/v1/jobs/${encodeURIComponent(jobId)}/sheets/${encodeURIComponent(sheetId)}/preview${query}`,
    { headers: { Accept: "image/png,image/*" } },
  );
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}

// structural members
export const patchMember = (jobId: string, memberId: string, member: Partial<MemberSpec>) =>
  apiFetch<JobRecord>(`/api/v1/jobs/${encodeURIComponent(jobId)}/members/${encodeURIComponent(memberId)}`, {
    method: "PATCH",
    body: { member },
  });

export const addMember = (jobId: string, member: MemberSpec) =>
  apiFetch<JobRecord>(`/api/v1/jobs/${encodeURIComponent(jobId)}/members`, { method: "POST", body: member });

export const deleteMember = (jobId: string, memberId: string) =>
  apiFetch<JobRecord>(`/api/v1/jobs/${encodeURIComponent(jobId)}/members/${encodeURIComponent(memberId)}`, {
    method: "DELETE",
  });

// fit-out items
export const patchItem = (jobId: string, itemId: string, item: Partial<FitoutItem>) =>
  apiFetch<JobRecord>(`/api/v1/jobs/${encodeURIComponent(jobId)}/items/${encodeURIComponent(itemId)}`, {
    method: "PATCH",
    body: { item },
  });

export const addItem = (jobId: string, item: FitoutItem) =>
  apiFetch<JobRecord>(`/api/v1/jobs/${encodeURIComponent(jobId)}/items`, { method: "POST", body: item });

export const deleteItem = (jobId: string, itemId: string) =>
  apiFetch<JobRecord>(`/api/v1/jobs/${encodeURIComponent(jobId)}/items/${encodeURIComponent(itemId)}`, {
    method: "DELETE",
  });

// measurement elements
/**
 * Replace the WHOLE element set read from the drawings (rooms, openings, walls, slabs,
 * members, misc + assumptions). The API recomputes the measurement sheet, BOQ and
 * materials and returns the refreshed job. Allowed when ready / approved / failed;
 * an edit on an approved job clears the approval.
 */
export const putElements = (jobId: string, elements: MeasurementExtraction) =>
  apiFetch<JobRecord>(`/api/v1/jobs/${encodeURIComponent(jobId)}/elements`, { method: "PUT", body: { elements } });

// lifecycle
export const recalculate = (jobId: string, body: { standards?: Standards; currency?: string } = {}) =>
  apiFetch<JobRecord>(`/api/v1/jobs/${encodeURIComponent(jobId)}/recalculate`, { method: "POST", body });

export const reprocess = (jobId: string) =>
  apiFetch<JobRecord>(`/api/v1/jobs/${encodeURIComponent(jobId)}/reprocess`, { method: "POST" });

export const approve = (jobId: string) =>
  apiFetch<JobRecord>(`/api/v1/jobs/${encodeURIComponent(jobId)}/approve`, { method: "POST" });

/** Send a ready / approved job back for rework; the reason lands in the job's timeline. */
export const rejectJob = (jobId: string, reason: string) => {
  const body: RejectRequest = { reason };
  return apiFetch<JobRecord>(`/api/v1/jobs/${encodeURIComponent(jobId)}/reject`, { method: "POST", body });
};

/**
 * Download the Excel export as a Blob (caller triggers the save). The file name comes from
 * the server's `Content-Disposition` header, falling back to `fallbackFilename`.
 */
export async function downloadExport(jobId: string, fallbackFilename = "measurement.xlsx"): Promise<BlobDownload> {
  const res = await apiRequest(`/api/v1/jobs/${encodeURIComponent(jobId)}/export.xlsx`, {
    headers: { Accept: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*" },
  });
  return { blob: await res.blob(), filename: filenameFromDisposition(res, fallbackFilename) };
}

// ---- standards -------------------------------------------------------------

export const getStandards = () => apiFetch<Standards>("/api/v1/standards");
export const putStandards = (body: Standards) => apiFetch<Standards>("/api/v1/standards", { method: "PUT", body });

// ---- admin -----------------------------------------------------------------

export const adminListUsers = () => apiFetch<UserProfile[]>("/api/v1/admin/users");
export const adminInvite = (body: InviteRequest) =>
  apiFetch<InviteResponse>("/api/v1/admin/invite", { method: "POST", body });
export const adminUpdateUser = (id: string, body: RoleUpdate) =>
  apiFetch<UserProfile>(`/api/v1/admin/users/${encodeURIComponent(id)}`, { method: "PATCH", body });
export const adminSetRole = (id: string, role: RoleUpdate["role"]) => adminUpdateUser(id, { role });
export const adminDeleteUser = (id: string) =>
  apiFetch<void>(`/api/v1/admin/users/${encodeURIComponent(id)}`, { method: "DELETE" });

/** Issue a fresh temporary password for a user (shown once, like an invite). */
export const adminResetPassword = (id: string) =>
  apiFetch<InviteResponse>(`/api/v1/admin/users/${encodeURIComponent(id)}/reset-password`, { method: "POST" });

/** Latest audit-log rows, newest first. The API wraps them as `{ items }`. */
export const adminAudit = (limit = 100) =>
  apiFetch<AuditListResponse>(`/api/v1/admin/audit?limit=${encodeURIComponent(String(limit))}`);

export const BACKUP_FALLBACK_FILENAME = "avighna-boq-backup.db";

/** Download a consistent SQLite snapshot as a Blob (caller triggers the save). */
export async function adminBackupBlob(): Promise<BlobDownload> {
  const res = await apiRequest("/api/v1/admin/backup", {
    headers: { Accept: "application/vnd.sqlite3,application/octet-stream,*/*" },
  });
  return { blob: await res.blob(), filename: filenameFromDisposition(res, BACKUP_FALLBACK_FILENAME) };
}
