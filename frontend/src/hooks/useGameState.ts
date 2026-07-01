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
  events: string[];
  startBattle: (runId: string) => Promise<void>;
  submitAction: (
    action: BattleAction,
    abilityId?: string,
  ) => Promise<void>;
}

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
  const [events, setEvents] = useState<string[]>([]);

  const startBattle = useCallback(async (id: string) => {
    setIsLoading(true);
    setError(null);
    setRunId(id);
    try {
      const res = await startBattleApi(id);
      setGameState(res.game_state);
      setCat(res.cat);
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setIsLoading(false);
    }
  }, []);

  const submitAction = useCallback(
    async (action: BattleAction, abilityId?: string) => {
      // Guard against concurrent submissions while a request is in flight, and
      // against acting before a battle has been started.
      if (isLoading || !runId) return;

      setIsLoading(true);
      setError(null);
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
        // the player can retry the action.
        setError(toErrorMessage(err));
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading, runId],
  );

  return {
    gameState,
    cat,
    isLoading,
    error,
    revival,
    gameOver,
    events,
    startBattle,
    submitAction,
  };
}
