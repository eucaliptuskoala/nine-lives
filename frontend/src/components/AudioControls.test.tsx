import { describe, it, expect, beforeEach, afterEach, vi } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

import { AudioProvider } from "../hooks/useAudio";
import AudioControls from "./AudioControls";

describe("AudioControls", () => {
  beforeEach(() => {
    localStorage.clear();
    // jsdom does not implement media playback.
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
  });

  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
  });

  it("renders a mute toggle and a volume slider", () => {
    render(
      <AudioProvider>
        <AudioControls />
      </AudioProvider>,
    );

    expect(screen.getByRole("button", { name: /mute audio/i })).toBeInTheDocument();
    expect(screen.getByRole("slider", { name: /volume/i })).toBeInTheDocument();
  });

  it("toggles mute state and persists it", () => {
    render(
      <AudioProvider>
        <AudioControls />
      </AudioProvider>,
    );

    fireEvent.click(screen.getByRole("button", { name: /mute audio/i }));

    // Label flips to the unmute affordance and preference is persisted.
    expect(
      screen.getByRole("button", { name: /unmute audio/i }),
    ).toBeInTheDocument();
    expect(localStorage.getItem("nl-audio-muted")).toBe("true");
  });

  it("updates the shared volume via the slider", () => {
    render(
      <AudioProvider>
        <AudioControls />
      </AudioProvider>,
    );

    const slider = screen.getByRole("slider", { name: /volume/i });
    fireEvent.change(slider, { target: { value: "0.8" } });

    expect(localStorage.getItem("nl-audio-volume")).toBe("0.8");
  });
});
