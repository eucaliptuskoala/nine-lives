import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/8bit/button";
import { getActiveGameRun } from "../api/data";

/**
 * Resolve a background image from `src/assets/backgrounds/` at build time.
 *
 * `import.meta.glob` is evaluated by Vite: if the user has dropped an image into
 * that folder it is bundled and hashed like any other asset; if the folder only
 * contains the README placeholder the map is empty and we fall back to a solid
 * color. Either way the build never breaks on a "missing" image.
 */
const backgroundModules = import.meta.glob(
  "../assets/backgrounds/*.{png,jpg,jpeg,webp}",
  { eager: true, query: "?url", import: "default" },
) as Record<string, string>;

const backgroundUrl: string | undefined = Object.values(backgroundModules)[0];

/**
 * Protected hub screen shown after winning a battle. It presents a fullscreen
 * background and a handful of location "nodes":
 *
 * - "Next Enemy"  → `/battle/:runId` (resumes the already-advanced round)
 * - "Memorial"    → `/memorial`
 * - "Rest"        → disabled placeholder (future feature)
 *
 * The current run id is resolved on mount through the backend
 * `GET /api/game-runs/active` endpoint so the page is refresh-safe and never
 * queries the database directly.
 *
 * Related: Requirements 25.5, 33.1–33.8
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

  // Solid retro fallback color is always applied; the image layers on top only
  // when one exists.
  const backgroundStyle: React.CSSProperties = {
    backgroundColor: "#0f172a",
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
      {/* Dark scrim so text/nodes stay legible over any background image. */}
      <div className="absolute inset-0 bg-black/50" aria-hidden="true" />

      <div className="relative z-10 flex w-full max-w-sm flex-col items-center gap-8 text-center">
        <h1 className="retro text-2xl font-bold text-white">Overworld</h1>

        {loading ? (
          <p role="status" className="retro text-xs text-gray-300">
            Loading...
          </p>
        ) : (
          <>
            {error && (
              <p role="alert" className="retro text-[10px] text-red-300">
                {error}
              </p>
            )}

            <div className="flex w-full max-w-[220px] flex-col items-stretch gap-4">
              <Button
                type="button"
                onClick={() => runId && navigate(`/battle/${runId}`)}
                disabled={!runId}
                className="h-auto bg-red-700 px-4 py-2 text-[10px] text-white"
              >
                Next Enemy
              </Button>

              <Button
                type="button"
                onClick={() => navigate("/memorial")}
                className="h-auto bg-gray-800 px-4 py-2 text-[10px] text-white"
              >
                Memorial
              </Button>

              {/* Placeholder for a future rest/heal node. */}
              <Button
                type="button"
                disabled
                aria-disabled="true"
                title="Coming soon"
                className="h-auto bg-gray-700 px-4 py-2 text-[10px] text-white opacity-60"
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
