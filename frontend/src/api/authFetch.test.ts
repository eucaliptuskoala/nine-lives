import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";

// Mock the Supabase client so we can control the active session/token.
const getSession = vi.fn();
vi.mock("../hooks/useSupabase", () => ({
  supabase: { auth: { getSession: () => getSession() } },
}));

import { authFetch, ApiError } from "./authFetch";

function mockSession(token: string | null) {
  getSession.mockResolvedValue({
    data: { session: token ? { access_token: token } : null },
  });
}

describe("authFetch", () => {
  beforeEach(() => {
    getSession.mockReset();
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("attaches the Authorization: Bearer header from the active session", async () => {
    mockSession("token-abc");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ ok: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    await authFetch("/api/game-runs", { method: "POST" });

    const [, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options.headers);
    expect(headers.get("Authorization")).toBe("Bearer token-abc");
  });

  it("throws a 401 ApiError when there is no active session token", async () => {
    mockSession(null);

    await expect(authFetch("/api/game-runs")).rejects.toMatchObject({
      status: 401,
    });
  });

  it("sets a JSON Content-Type when a non-FormData body is provided", async () => {
    mockSession("token-abc");
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    await authFetch("/api/battle/action", {
      method: "POST",
      body: JSON.stringify({ run_id: "r1", action: "attack" }),
    });

    const [, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options.headers);
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it("does not override an existing Content-Type and skips it for FormData", async () => {
    mockSession("token-abc");
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    const form = new FormData();
    form.append("k", "v");
    await authFetch("/api/x", { method: "POST", body: form });

    const [, options] = fetchMock.mock.calls[0];
    const headers = new Headers(options.headers);
    expect(headers.has("Content-Type")).toBe(false);
  });

  it("throws an ApiError with the status on non-ok responses", async () => {
    mockSession("token-abc");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "Forbidden" }), {
        status: 403,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const err = await authFetch("/api/cats/c1/note", {
      method: "PATCH",
      body: JSON.stringify({ note: "hi" }),
    }).catch((e) => e);

    expect(err).toBeInstanceOf(ApiError);
    if (err instanceof ApiError) {
      expect(err.status).toBe(403);
      expect(err.message).toBe("Forbidden");
    }
  });

  it("returns undefined for empty 204 responses", async () => {
    mockSession("token-abc");
    const fetchMock = vi
      .fn()
      .mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    const result = await authFetch("/api/game-runs", { method: "POST" });
    expect(result).toBeUndefined();
  });

  it("parses and returns the JSON body on success", async () => {
    mockSession("token-abc");
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ run_id: "r1", status: "DIGITIZING" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const result = await authFetch<{ run_id: string; status: string }>(
      "/api/game-runs",
      { method: "POST" },
    );
    expect(result).toEqual({ run_id: "r1", status: "DIGITIZING" });
  });
});
