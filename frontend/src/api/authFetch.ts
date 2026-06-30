import { supabase } from "../hooks/useSupabase";

/**
 * Base URL for the backend API. Mirrors the convention used in `digitize.ts`.
 */
export const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/**
 * Error thrown when an authenticated request fails. Carries the HTTP status so
 * callers can branch on auth failures (401), forbidden access (403), etc.
 */
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

/**
 * Shared authenticated-fetch wrapper for endpoints that REQUIRE a Supabase JWT.
 *
 * Pulls the access token from the active session via `supabase.auth.getSession()`
 * and sets the `Authorization: Bearer <token>` header on the request. This is the
 * standard way to call the Battle API and the authenticated Data API endpoints.
 *
 * Note: `POST /api/digitize` is an open mock endpoint and intentionally does NOT
 * use this helper (see `digitize.ts`).
 *
 * @param path API path beginning with `/` (e.g. `/api/battle/start`).
 * @param options Standard `fetch` options. The `Authorization` header is added
 *   automatically; a JSON `Content-Type` is added when a body is present unless
 *   the caller already set one or the body is `FormData`.
 * @returns The parsed JSON response body (or `undefined` for empty `204` responses).
 * @throws {ApiError} When no active session/token exists, or when the response is non-ok.
 */
export async function authFetch<T = unknown>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const token = session?.access_token;
  if (!token) {
    throw new ApiError(401, "Not authenticated: no active session token");
  }

  const headers = new Headers(options.headers);
  headers.set("Authorization", `Bearer ${token}`);

  // Default to JSON content type when sending a non-FormData body and the caller
  // has not already specified one.
  if (
    options.body !== undefined &&
    options.body !== null &&
    !(options.body instanceof FormData) &&
    !headers.has("Content-Type")
  ) {
    headers.set("Content-Type", "application/json");
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });

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
