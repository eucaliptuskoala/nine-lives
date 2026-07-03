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

/**
 * Response from `GET /api/game-runs/active`. Both fields are null when the
 * authenticated user has no active (IN_PROGRESS + ALIVE cat) run.
 */
export interface ActiveGameRunResponse {
  run_id: string | null;
  cat: Cat | null;
}

/** Creates a new game run for the authenticated user. Requires auth. */
export function createGameRun(): Promise<CreateGameRunResponse> {
  return authFetch<CreateGameRunResponse>("/api/game-runs", {
    method: "POST",
  });
}

/**
 * Fetches the authenticated user's active game run (most recent IN_PROGRESS run
 * whose cat is ALIVE), or `{ run_id: null, cat: null }` when none exists.
 * Requires auth.
 */
export function getActiveGameRun(): Promise<ActiveGameRunResponse> {
  return authFetch<ActiveGameRunResponse>("/api/game-runs/active", {
    method: "GET",
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
