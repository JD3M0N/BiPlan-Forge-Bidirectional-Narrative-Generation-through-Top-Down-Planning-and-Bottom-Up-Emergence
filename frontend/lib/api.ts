const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type RequestOptions = Omit<RequestInit, "body"> & {
  body?: unknown;
};

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

type FastApiValidationError = {
  loc?: Array<string | number>;
  msg?: string;
  type?: string;
};

function formatApiDetail(detail: unknown): string {
  if (!detail) {
    return "Request failed";
  }

  if (typeof detail === "string") {
    return detail;
  }

  if (Array.isArray(detail)) {
    const messages = detail
      .map((item) => {
        if (typeof item === "string") {
          return item;
        }

        if (item && typeof item === "object") {
          const validation = item as FastApiValidationError;
          const field = validation.loc?.filter((part) => part !== "body").join(".");
          if (validation.msg && field) {
            return `${field}: ${validation.msg}`;
          }
          if (validation.msg) {
            return validation.msg;
          }
        }

        return JSON.stringify(item);
      })
      .filter(Boolean);

    return messages.length > 0 ? messages.join("; ") : "Request failed";
  }

  if (typeof detail === "object") {
    const payload = detail as { message?: unknown; error?: unknown };
    if (typeof payload.message === "string") {
      return payload.message;
    }
    if (typeof payload.error === "string") {
      return payload.error;
    }
    return JSON.stringify(detail);
  }

  return String(detail);
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
    cache: "no-store",
  });

  if (!response.ok) {
    let detail = "Request failed";
    try {
      const payload = (await response.json()) as { detail?: unknown };
      detail = formatApiDetail(payload.detail);
    } catch {}
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
