import { useState, useEffect, useCallback } from "react";
import type { Cat } from "../types/game";
import { getMemorialCats, updateCatNote } from "../api/data";
import { ApiError } from "../api/authFetch";

export const NOTE_MAX_LENGTH = 500;

export interface UseMemorialReturn {
  cats: Cat[];
  loading: boolean;
  error: string | null;
  updateNote: (catId: string, note: string) => Promise<void>;
}

/**
 * Loads the authenticated user's MEMORIAL cats and updates their personal
 * notes via the backend Data API. Contains no direct Supabase database access —
 * the Supabase client is used only (indirectly, via `authFetch`) to obtain the
 * auth token.
 */
export function useMemorial(): UseMemorialReturn {
  const [cats, setCats] = useState<Cat[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchMemorial = async () => {
      try {
        const data = await getMemorialCats();
        if (!cancelled) setCats(data);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof ApiError
              ? err.message
              : "Failed to load memorial cats",
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchMemorial();

    return () => {
      cancelled = true;
    };
  }, []);

  const updateNote = useCallback(
    async (catId: string, note: string): Promise<void> => {
      if (note.length > NOTE_MAX_LENGTH) {
        setError(`Note must be ${NOTE_MAX_LENGTH} characters or fewer`);
        return;
      }

      setError(null);
      try {
        const updated = await updateCatNote(catId, note);
        setCats((prev) =>
          prev.map((cat) => (cat.id === updated.id ? updated : cat)),
        );
      } catch (err) {
        setError(
          err instanceof ApiError ? err.message : "Failed to update note",
        );
      }
    },
    [],
  );

  return { cats, loading, error, updateNote };
}
