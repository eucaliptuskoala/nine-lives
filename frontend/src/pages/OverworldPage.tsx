import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/8bit/button";
import { getActiveGameRun } from "../api/data";

/**
 * Protected hub screen after winning a battle. Shows location nodes:
 * Next Enemy, Memorial, and Rest (disabled placeholder).
 */
function OverworldPage() {
  const navigate = useNavigate();

  const [runId, setRunId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(null);

    getActiveGameRun()
      .then((res) => {
        if (!active) return;
        setRunId(res.run_id);
        if (!res.run_id) {
          setError("No active run found.");
        }
      })
      .catch(() => {
        if (active) setError("Could not load your run. Please try again.");
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, []);

  const backgroundStyle: React.CSSProperties = {
    backgroundColor: "#1B1A22",
    ...(backgroundUrl
      ? {
          backgroundImage: `url(${backgroundUrl})`,
          backgroundSize: "cover",
          backgroundPosition: "center",
          backgroundRepeat: "no-repeat",
        }
      : {}),
  };

  return (
    <div
      className="relative flex min-h-screen flex-col items-center justify-center px-4 py-10"
      style={backgroundStyle}
    >
      {/* Dark scrim for text legibility over background image. */}
      <div className="absolute inset-0 bg-black/50" aria-hidden="true" />

      <div className="relative z-10 flex w-full max-w-sm flex-col items-center gap-8 text-center">
        <h1 className="retro text-2xl font-bold text-text-primary">Overworld</h1>

        {loading ? (
          <p role="status" className="retro text-xs text-text-secondary">
            Loading...
          </p>
        ) : (
          <>
            {error && (
              <p role="alert" className="retro text-[10px] text-hp">
                {error}
              </p>
            )}

            <div className="flex w-full max-w-[220px] flex-col items-stretch gap-4">
              <Button
                type="button"
                onClick={() => runId && navigate(`/battle/${runId}`)}
                disabled={!runId}
                className="h-auto bg-accent hover:bg-accent/90 px-4 py-2 text-[10px] text-app"
              >
                Next Enemy
              </Button>

              <Button
                type="button"
                onClick={() => navigate("/memorial")}
                className="h-auto bg-btn hover:bg-btn-hover active:bg-btn-pressed px-4 py-2 text-[10px] text-btn-text"
              >
                Memorial
              </Button>

              <Button
                type="button"
                disabled
                aria-disabled="true"
                title="Coming soon"
                className="h-auto bg-btn px-4 py-2 text-[10px] text-text-disabled opacity-60"
              >
                Rest (soon)
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default OverworldPage;
