import { authFetch } from "./authFetch";
import type { GameState, Cat } from "../types/game";

/**
 * Battle API client. Both endpoints REQUIRE a valid Supabase JWT, so every call
 * goes through the shared {@link authFetch} wrapper.
 *
 * These are thin typed wrappers; the consuming hooks/pages are wired up in a
 * later task (5.x).
 */

/** A single battle action submitted by the player. */
export type BattleAction = "attack" | "defend" | "ability";

/** Request body for `POST /api/battle/action`. */
export interface BattleActionRequest {
  run_id: string;
  action: BattleAction;
  ability_id?: string;
}

/** Response from `POST /api/battle/start`. */
export interface BattleStateResponse {
  game_state: GameState;
  cat: Cat;
}

/** Response from `POST /api/battle/action`. */
export interface BattleActionResponse {
  game_state: GameState;
  cat: Cat;
  revival: boolean;
  game_over: boolean;
  events: string[];
}

/** Starts (or resumes) the battle for a game run. Requires auth. */
export function startBattle(runId: string): Promise<BattleStateResponse> {
  return authFetch<BattleStateResponse>("/api/battle/start", {
    method: "POST",
    body: JSON.stringify({ run_id: runId }),
    timeoutMs: 10000,
  });
}

/** Submits a player action and returns the resolved battle state. Requires auth. */
export function submitAction(
  body: BattleActionRequest,
): Promise<BattleActionResponse> {
  return authFetch<BattleActionResponse>("/api/battle/action", {
    method: "POST",
    body: JSON.stringify(body),
    timeoutMs: 5000,
  });
}
