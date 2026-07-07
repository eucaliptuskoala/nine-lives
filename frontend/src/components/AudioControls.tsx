import { Button } from "@/components/ui/8bit/button";
import { useAudio } from "../hooks/useAudio";

/**
 * Small floating audio control shown on EVERY page (including the public Home
 * and Login pages). Governs both the ambient music and the per-move sound
 * effects via the shared {@link useAudio} state.
 *
 * Positioned bottom-left so it never overlaps the top-right sign-out control in
 * {@link AppHeader}.
 */
function AudioControls() {
  const { muted, toggleMute, volume, setVolume } = useAudio();

  return (
    <div className="fixed bottom-3 left-3 z-50 flex items-center gap-2">
      <Button
        type="button"
        onClick={toggleMute}
        aria-label={muted ? "Unmute audio" : "Mute audio"}
        aria-pressed={muted}
        title={muted ? "Unmute" : "Mute"}
        className="h-auto bg-btn hover:bg-btn-hover active:bg-btn-pressed px-3 py-1.5 text-[12px] text-btn-text"
      >
        {muted ? "\uD83D\uDD07" : "\uD83D\uDD0A"}
      </Button>

      <input
        type="range"
        min={0}
        max={1}
        step={0.05}
        value={muted ? 0 : volume}
        onChange={(e) => setVolume(Number.parseFloat(e.target.value))}
        aria-label="Volume"
        className="h-1 w-20 cursor-pointer accent-accent"
      />
    </div>
  );
}

export default AudioControls;
