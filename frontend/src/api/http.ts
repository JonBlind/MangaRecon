const BASE_URL = import.meta.env.VITE_API_BASE_URL;

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

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      ...(options.headers ?? {}),
      "Content-Type": "application/json",
    },
  });

  const json = await readJsonSafe(res);

  if (!res.ok || json?.status === "error") {
    const msg = json?.message || json?.detail || `Request failed (${res.status})`;
    throw new ApiRequestError(msg, res.status);
  }

  return json?.data ?? (json as T);
}
