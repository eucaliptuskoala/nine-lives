import { supabase } from "../hooks/useSupabase";

export const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;

  constructor(status: number, message: string, body?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

/** Default request timeout (ms). */
export const DEFAULT_TIMEOUT_MS = 15000;

/** Options accepted by {@link authFetch} on top of the standard `fetch` options. */
export interface AuthFetchOptions extends RequestInit {
    timeoutMs?: number;
}

/**
 * @param path API path beginning with `/` (e.g. `/api/battle/start`).
 * @param options Standard `fetch` options plus an optional `timeoutMs`.
 * @returns The parsed JSON response body (or `undefined` for empty `204` responses).
 * @throws {ApiError} When no active session/token exists, when the request times
 *   out (status 408), or when the response is non-ok.
 */
export async function authFetch<T = unknown>(
  path: string,
  options: AuthFetchOptions = {},
): Promise<T> {
  const { timeoutMs = DEFAULT_TIMEOUT_MS, signal, ...rest } = options;

  const {
    data: { session },
  } = await supabase.auth.getSession();

  const token = session?.access_token;
  if (!token) {
    throw new ApiError(401, "Not authenticated: no active session token");
  }

  const headers = new Headers(rest.headers);
  headers.set("Authorization", `Bearer ${token}`);

  // Default to JSON content type when sending a non-FormData body and the caller
  // has not already specified one.
  if (
    rest.body !== undefined &&
    rest.body !== null &&
    !(rest.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  // Abort the request once the timeout elapses. If the caller passed their own
  // signal, honor it too by aborting our controller when theirs fires.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  if (signal) {
    if (signal.aborted) {
      controller.abort();
    } else {
      signal.addEventListener("abort", () => controller.abort(), {
        once: true,
      });
    }
  }

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      ...rest,
      headers,
      signal: controller.signal,
    });
  } catch (err) {
    // Distinguish a timeout/abort from other network errors.
    if (controller.signal.aborted) {
      throw new ApiError(408, "Request timed out. Please try again.");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    const body = await safeParseBody(res);
    const message =
      (typeof body === "object" && body !== null && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : undefined) ?? `Request to ${path} failed with status ${res.status}`;
    throw new ApiError(res.status, message, body);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  return safeParseBody(res) as Promise<T>;
}

/** Parses a response body as JSON, falling back to text when JSON parsing fails. */
async function safeParseBody(res: Response): Promise<unknown> {
  const text = await res.text();
  if (!text) return undefined;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}
