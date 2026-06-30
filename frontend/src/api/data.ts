import { authFetch } from "./authFetch";
import type { Cat, GameStatus } from "../types/game";

/**
 * Data API client. Every endpoint REQUIRES a valid Supabase JWT and enforces
 * ownership against the authenticated user server-side, so all calls go through
 * the shared {@link authFetch} wrapper.
 *
 * These are thin typed wrappers; the consuming hooks/pages are wired up in
 * later tasks (6.x / 7.x).
 */

/** Response from `POST /api/game-runs`. */
export interface CreateGameRunResponse {
  run_id: string;
  status: GameStatus; // always DIGITIZING on creation
}

/** Creates a new game run for the authenticated user. Requires auth. */
export function createGameRun(): Promise<CreateGameRunResponse> {
  return authFetch<CreateGameRunResponse>("/api/game-runs", {
    method: "POST",
  });
}

/** Lists the authenticated user's MEMORIAL cats. Requires auth. */
export function getMemorialCats(): Promise<Cat[]> {
  return authFetch<Cat[]>("/api/cats/memorial", {
    method: "GET",
  });
}

/** Updates the personal note for a cat the authenticated user owns. Requires auth. */
export function updateCatNote(catId: string, note: string): Promise<Cat> {
  return authFetch<Cat>(`/api/cats/${catId}/note`, {
    method: "PATCH",
    body: JSON.stringify({ note }),
  });
}
