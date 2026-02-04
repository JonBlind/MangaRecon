import type { ApiEnvelope } from "../types/api";

const BASE_URL = import.meta.env.VITE_API_BASE_URL;

if (!BASE_URL) {
  throw new Error("VITE_API_BASE_URL is not set. Add it to frontend/.env and restart Vite.");
}
export class ApiRequestError extends Error {
  statusCode?: number;
  constructor(message: string, statusCode?: number) {
    super(message);
    this.name = "ApiRequestError";
    this.statusCode = statusCode;
  }
}

async function readJsonSafe(res: Response): Promise<any> {
  const text = await res.text();
  try {
    return text ? JSON.parse(text) : null;
  } catch {
    return null;
  }
}

function extractErrorMessage(json: any, status: number): string {
  if (!json) return `Request failed (${status})`;

  const detail = json.detail;

  // If backend uses a generic message, prefer the real detail
  const generic = json.message === "Error" || json.message === "Validation error";

  if (generic) {
    if (typeof detail === "string" && detail.trim()) return detail;

    if (Array.isArray(detail) && detail.length) {
      const first = detail[0];
      const msg = typeof first?.msg === "string" ? first.msg : null;

      const locArr = Array.isArray(first?.loc) ? first.loc : [];
      const loc = locArr.filter((x: any) => x !== "body").join(".");

      if (msg && loc) return `${loc}: ${msg}`;
      if (msg) return msg;
    }

    if (detail && typeof detail === "object") {
      if (typeof detail.reason === "string" && detail.reason.trim()) return detail.reason;
      if (typeof detail.message === "string" && detail.message.trim()) return detail.message;
      if (typeof detail.code === "string" && detail.code.trim()) return detail.code;
    }

    return json.message;
  }

  if (typeof json.message === "string" && json.message.trim()) return json.message;

  if (typeof detail === "string" && detail.trim()) return detail;

  return `Request failed (${status})`;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<ApiEnvelope<T>> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
  });

  const json = await readJsonSafe(res);

  if (!res.ok || json?.status === "error") {
    const msg =
      json?.message ||
      json?.detail ||
      `Request failed (${res.status})`;
    throw new ApiRequestError(msg, res.status);
  }

  return json as ApiEnvelope<T>;
}
