import { useState, useCallback } from "react";
import type { GameState, Cat } from "../types/game";
import {
  startBattle as startBattleApi,
  submitAction as submitActionApi,
  type BattleAction,
} from "../api/battle";
import { ApiError } from "../api/authFetch";

/**
 * Thin API wrapper hook for the Battle system. Contains NO combat math — it
 * simply calls the Battle API and reflects whatever state the backend returns.
 * The backend is the authoritative game engine.
 */
export interface UseGameStateReturn {
  gameState: GameState | null;
  cat: Cat | null;
  isLoading: boolean;
  error: string | null;
  revival: boolean;
  gameOver: boolean;
  /** True when a request failed with 401 — the session expired mid-battle. */
  sessionExpired: boolean;
  /** True when a request failed with 409 — the run has already ended. */
  runEnded: boolean;
  events: string[];
  startBattle: (runId: string) => Promise<void>;
  submitAction: (
    action: BattleAction,
    abilityId?: string,
  ) => Promise<void>;
}

/** Session-storage key used to remember the run to resume after re-login. */
export const PENDING_RUN_KEY = "nl-pending-run";

function toErrorMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  if (err instanceof Error) return err.message;
  return "Something went wrong. Please try again.";
}

export function useGameState(): UseGameStateReturn {
  const [gameState, setGameState] = useState<GameState | null>(null);
  const [cat, setCat] = useState<Cat | null>(null);
  const [runId, setRunId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [revival, setRevival] = useState(false);
  const [gameOver, setGameOver] = useState(false);
  const [sessionExpired, setSessionExpired] = useState(false);
  const [runEnded, setRunEnded] = useState(false);
  const [events, setEvents] = useState<string[]>([]);

  // Centralized recovery for the two special Battle API failure modes:
  //  - 401: the session expired mid-battle. Persist the run so the user can be
  //    returned to it after re-authenticating, and flag `sessionExpired`.
  //  - 409: the run has already ended. Flag `runEnded` so the UI can offer
  //    navigation to the memorial.
  // Everything else falls through to the generic, retry-friendly error message.
  const handleError = useCallback((err: unknown, id: string | null) => {
    if (err instanceof ApiError && err.status === 401) {
      if (id) sessionStorage.setItem(PENDING_RUN_KEY, id);
      setSessionExpired(true);
      setError("Your session has expired. Please sign in again.");
      return;
    }
    if (err instanceof ApiError && err.status === 409) {
      setRunEnded(true);
      setError("This game has already ended.");
      return;
    }
    setError(toErrorMessage(err));
  }, []);

  const startBattle = useCallback(
    async (id: string) => {
      setIsLoading(true);
      setError(null);
      setSessionExpired(false);
      setRunEnded(false);
      setRunId(id);
      try {
        const res = await startBattleApi(id);
        setGameState(res.game_state);
        setCat(res.cat);
      } catch (err) {
        handleError(err, id);
      } finally {
        setIsLoading(false);
      }
    },
    [handleError],
  );

  const submitAction = useCallback(
    async (action: BattleAction, abilityId?: string) => {
      // Guard against concurrent submissions while a request is in flight, and
      // against acting before a battle has been started.
      if (isLoading || !runId) return;

      setIsLoading(true);
      setError(null);
      setSessionExpired(false);
      setRunEnded(false);
      try {
        const res = await submitActionApi({
          run_id: runId,
          action,
          ability_id: abilityId,
        });
        setGameState(res.game_state);
        setCat(res.cat);
        setRevival(res.revival);
        setGameOver(res.game_over);
        setEvents(res.events);
      } catch (err) {
        // On failure, leave gameState untouched so buttons can re-enable and
        // the player can retry the action. Special-case 401/409 recovery.
        handleError(err, runId);
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, runId, handleError],
  );

  return {
    gameState,
    cat,
    isLoading,
    error,
    revival,
    gameOver,
    sessionExpired,
    runEnded,
    events,
    startBattle,
    submitAction,
  };
}
