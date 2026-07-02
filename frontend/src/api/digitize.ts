import type { Cat } from "../types/game";

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/**
 * Parameters accepted by the digitize endpoint alongside the uploaded photo.
 * These map to the backend `/api/digitize` form fields.
 */
export interface DigitizeParams {
  /** The game run this cat belongs to (`game_run_id`). */
  gameRunId: string;
  /** The authenticated user's id (`user_id`). */
  userId: string;
  /** Required cat name (`cat_name`). */
  catName: string;
  /** Optional free-text personality description (`personality`). */
  personality?: string;
}

/**
 * Upload a cat photo to the digitize endpoint and return the created {@link Cat}.
 *
 * Digitize is an OPEN mock endpoint — it requires no auth token, so this uses a
 * plain `fetch` (not `authFetch`). The file plus metadata are sent as multipart
 * form data.
 */
export async function uploadCatPhoto(
  file: File,
  params: DigitizeParams,
): Promise<Cat> {
  const form = new FormData();
  form.append("file", file);
  form.append("game_run_id", params.gameRunId);
  form.append("user_id", params.userId);
  form.append("cat_name", params.catName);
  if (params.personality && params.personality.length > 0) {
    form.append("personality", params.personality);
  }

  // Digitization can be slow (image processing on the backend); allow up to 30s
  // before aborting and surfacing a friendly timeout message.
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30000);

  let res: Response;
  try {
    res = await fetch(`${API_BASE}/api/digitize`, {
      method: "POST",
      body: form,
      signal: controller.signal,
    });
  } catch (err) {
    if (controller.signal.aborted) {
      throw new Error("Digitization timed out. Please try again.");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }

  if (!res.ok) {
    let message = `Digitization failed (${res.status})`;
    try {
      const data = await res.json();
      if (data && typeof data.detail === "string") {
        message = data.detail;
      }
    } catch {
      // Response body wasn't JSON — keep the default message.
    }
    throw new Error(message);
  }

  return (await res.json()) as Cat;
}
