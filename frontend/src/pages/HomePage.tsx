import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/8bit/button";
import { useAuth } from "../hooks/useSupabase";
import { getActiveGameRun } from "../api/data";

/**
 * Public landing page at `/`. Adapts content based on auth state:
 * signed out → sign in; signed in → new game, continue, memorial.
 */
function HomePage() {
  const navigate = useNavigate();
  const { user, loading: authLoading } = useAuth();

  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const [runLoading, setRunLoading] = useState(false);

  useEffect(() => {
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
        if (active) setActiveRunId(null);
      })
      .finally(() => {
        if (active) setRunLoading(false);
      });

    return () => {
      active = false;
    };
  }, [authLoading, user]);

  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center px-4">
        <p role="status" className="retro text-xs text-text-secondary">
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
            <p className="text-text-secondary">
              Digitize your cat, battle through the arena, and see how many of
              its nine lives you can spend.
            </p>
            <Button
              type="button"
              onClick={() => navigate("/login")}
              className="h-auto bg-accent hover:bg-accent/90 px-4 py-2 text-[10px] text-app"
            >
              Sign In
            </Button>
          </div>
        ) : (
          // ---- Logged in ----
          <div className="flex flex-col items-center gap-6">
            <p className="text-text-secondary">
              Welcome back. Start a new game, continue an ongoing run, or visit
              the memorial for cats that have spent all nine lives.
            </p>

            <div className="flex flex-col items-stretch gap-4 w-full max-w-[220px]">
              {activeRunId && (
                <Button
                  type="button"
                  onClick={() => navigate(`/battle/${activeRunId}`)}
                  className="h-auto bg-accent hover:bg-accent/90 px-4 py-2 text-[10px] text-app"
                >
                  Continue
                </Button>
              )}

              <Button
                type="button"
                onClick={() => navigate("/digitize")}
                className="h-auto bg-accent hover:bg-accent/90 px-4 py-2 text-[10px] text-app"
              >
                New Game
              </Button>

              <Button
                type="button"
                onClick={() => navigate("/memorial")}
                className="h-auto bg-btn hover:bg-btn-hover active:bg-btn-pressed px-4 py-2 text-[10px] text-btn-text"
              >
                Memorial
              </Button>
            </div>

            {runLoading && (
              <p role="status" className="retro text-[10px] text-text-secondary">
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
