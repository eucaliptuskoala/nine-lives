import type { Cat } from "../types/game";
import { supabase } from "../hooks/useSupabase";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const POLL_INTERVAL_MS = 2000;
const MAX_WAIT_MS = 300000; // 5 minutes
const START_TIMEOUT_MS = 30000; // 30s to get a task_id

export interface DigitizeParams {
  gameRunId: string;
  catName: string;
  personality?: string;
}

/**
 * Reads the current Supabase access token and returns it as an `Authorization`
 * header. Intentionally NOT routed through the shared `authFetch` helper — this
 * module drives its own long-poll loop with its own `AbortController`/timeout
 * semantics, and `authFetch`'s fixed short timeout and JSON-only parsing are a
 * poor fit here. Called before the initial POST and again before every status
 * poll so a token refreshed by supabase-js mid-poll is picked up.
 */
async function getAuthHeaders(): Promise<Record<string, string>> {
  const {
    data: { session },
  } = await supabase.auth.getSession();

  const token = session?.access_token;
  if (!token) {
    throw new Error("Not authenticated: no active session token");
  }

  return { Authorization: `Bearer ${token}` };
}

export async function uploadCatPhoto(
  file: File,
  params: DigitizeParams,
): Promise<Cat> {
  const form = new FormData();
  form.append("file", file);
  form.append("game_run_id", params.gameRunId);
  form.append("cat_name", params.catName);
  if (params.personality && params.personality.length > 0) {
    form.append("personality", params.personality);
  }

  let taskId: string;

  const startController = new AbortController();
  const startTimer = setTimeout(() => startController.abort(), START_TIMEOUT_MS);

  try {
    const authHeaders = await getAuthHeaders();
    const startRes = await fetch(`${API_BASE}/api/digitize`, {
      method: "POST",
      body: form,
      headers: authHeaders,
      signal: startController.signal,
    });

    if (!startRes.ok) {
      let message = `Digitization failed (${startRes.status})`;
      try {
        const data = await startRes.json();
        if (data && typeof data.detail === "string") {
          message = data.detail;
        }
      } catch {
        // keep default message
      }
      throw new Error(message);
    }

    const { task_id } = await startRes.json();
    taskId = task_id;
  } catch (err) {
    if (startController.signal.aborted) {
      throw new Error("Digitization timed out. Please try again.");
    }
    throw err;
  } finally {
    clearTimeout(startTimer);
  }

  const deadline = Date.now() + MAX_WAIT_MS;

  while (Date.now() < deadline) {
    await new Promise((r) => setTimeout(r, POLL_INTERVAL_MS));

    // Fetched outside the try/catch below so an auth failure propagates and
    // aborts the poll instead of being silently retried as a transient
    // network blip.
    const pollAuthHeaders = await getAuthHeaders();

    let statusRes: Response;
    try {
      statusRes = await fetch(`${API_BASE}/api/digitize/status/${taskId}`, {
        headers: pollAuthHeaders,
      });
    } catch {
      continue;
    }

    if (!statusRes.ok) {
      continue;
    }

    let data: { status: string; result?: Cat; error?: string };
    try {
      data = await statusRes.json();
    } catch {
      continue;
    }

    if (data.status === "COMPLETED") {
      if (!data.result) {
        throw new Error("Digitization completed but no result was returned.");
      }
      return data.result;
    }

    if (data.status === "FAILED") {
      throw new Error(data.error || "Digitization failed on the server.");
    }
  }

  throw new Error("Digitization timed out. Please try again.");
}
