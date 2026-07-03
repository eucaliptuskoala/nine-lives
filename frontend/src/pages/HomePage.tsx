import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/8bit/button";
import { useAuth } from "../hooks/useSupabase";
import { getActiveGameRun } from "../api/data";

/**
 * Public landing page served at `/`. It renders OUTSIDE the AuthGuard and never
 * forces a redirect — instead it adapts its content to the current auth state:
 *
 * - Signed out: a tagline + "Sign In" control (→ `/login`).
 * - Signed in: an intro + "New Game" (→ `/digitize`), "Memorial" (→ `/memorial`),
 *   and, when the user has an active run, a "Continue" control (→ `/battle/:runId`).
 *
 * The active-run lookup goes through the backend `GET /api/game-runs/active`
 * endpoint (never a direct DB query).
 *
 * Related: Requirements 25.1, 25.2, 32.1–32.6
 */
function HomePage() {
  const navigate = useNavigate();
  const { user, loading: authLoading } = useAuth();

  // Active-run lookup state (only meaningful when the user is signed in).
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [runLoading, setRunLoading] = useState(false);

  useEffect(() => {
    // Only look up an active run for authenticated users.
    if (authLoading || !user) {
      setActiveRunId(null);
      return;
    }

    let active = true;
    setRunLoading(true);

    getActiveGameRun()
      .then((res) => {
        if (active) setActiveRunId(res.run_id);
      })
      .catch(() => {
        // On error we simply don't offer "Continue" — the user can still start
        // a new game.
        if (active) setActiveRunId(null);
      })
      .finally(() => {
        if (active) setRunLoading(false);
      });

    return () => {
      active = false;
    };
  }, [authLoading, user]);

  // Minimal loading state while the initial session lookup resolves.
  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <p role="status" className="retro text-xs text-gray-400">
          Loading...
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-screen gap-8 px-4 py-10">
      <div className="w-full max-w-sm flex flex-col items-center gap-8 text-center">
        <h1 className="retro text-3xl font-bold">Nine Lives</h1>

        {!user ? (
          // ---- Logged out ----
          <div className="flex flex-col items-center gap-6">
            <p className="text-gray-500">
              Digitize your cat, battle through the arena, and see how many of
              its nine lives you can spend.
            </p>
            <Button
              type="button"
              onClick={() => navigate("/login")}
              className="h-auto bg-indigo-600 px-4 py-2 text-[10px] text-white"
            >
              Sign In
            </Button>
          </div>
        ) : (
          // ---- Logged in ----
          <div className="flex flex-col items-center gap-6">
            <p className="text-gray-500">
              Welcome back. Start a new game, continue an ongoing run, or visit
              the memorial for cats that have spent all nine lives.
            </p>

            <div className="flex flex-col items-stretch gap-4 w-full max-w-[220px]">
              {activeRunId && (
                <Button
                  type="button"
                  onClick={() => navigate(`/battle/${activeRunId}`)}
                  className="h-auto bg-emerald-600 px-4 py-2 text-[10px] text-white"
                >
                  Continue
                </Button>
              )}

              <Button
                type="button"
                onClick={() => navigate("/digitize")}
                className="h-auto bg-indigo-600 px-4 py-2 text-[10px] text-white"
              >
                New Game
              </Button>

              <Button
                type="button"
                onClick={() => navigate("/memorial")}
                className="h-auto bg-gray-800 px-4 py-2 text-[10px] text-white"
              >
                Memorial
              </Button>
            </div>

            {runLoading && (
              <p role="status" className="retro text-[10px] text-gray-400">
                Checking for an active run...
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default HomePage;
