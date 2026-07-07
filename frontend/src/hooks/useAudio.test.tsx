import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import "@testing-library/jest-dom/vitest";

// Deterministic playlist + effect map so we can assert advancing/wrapping and
// per-move mapping without depending on the real assets on disk.
vi.mock("./audioAssets", () => ({
  AMBIENT_TRACKS: ["/track-0.wav", "/track-1.wav", "/track-2.wav"],
  SOUND_EFFECTS: {
    attack_sound: "/attack.wav",
    block_sound: "/block.wav",
    ability_sound: "/ability.wav",
    ultimate_sound: "/ultimate.wav",
  },
  MOVE_SOUND_MAP: {
    attack: "attack_sound",
    defend: "block_sound",
    ability: "ability_sound",
    ultimate: "ultimate_sound",
  },
}));

import { AudioProvider, useAudio, nextTrackIndex } from "./useAudio";

// --- Mock the HTML5 Audio constructor used by playMoveSound (sound effects) ---
class MockAudio {
  static instances: MockAudio[] = [];
  src: string;
  volume = 1;
  play = vi.fn().mockResolvedValue(undefined);
  constructor(src?: string) {
    this.src = src ?? "";
    MockAudio.instances.push(this);
  }
}

/** Small consumer that surfaces the shared audio state for assertions. */
function AudioConsumer() {
  const { muted, toggleMute, volume, playMoveSound } = useAudio();
  return (
    <div>
      <span data-testid="muted">{String(muted)}</span>
      <span data-testid="volume">{volume}</span>
      <button onClick={toggleMute}>toggle</button>
      <button onClick={() => playMoveSound("attack")}>attack</button>
      <button onClick={() => playMoveSound("defend")}>defend</button>
      <button onClick={() => playMoveSound("ability")}>ability</button>
      <button onClick={() => playMoveSound("ultimate")}>ultimate</button>
    </div>
  );
}

describe("useAudio / AudioProvider", () => {
  beforeEach(() => {
    localStorage.clear();
    MockAudio.instances = [];
    vi.stubGlobal("Audio", MockAudio as unknown as typeof Audio);
    // jsdom does not implement media playback — stub so nothing throws/logs.
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue(undefined);
    vi.spyOn(HTMLMediaElement.prototype, "pause").mockImplementation(() => {});
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it("nextTrackIndex advances and wraps around the playlist", () => {
    expect(nextTrackIndex(0, 3)).toBe(1);
    expect(nextTrackIndex(1, 3)).toBe(2);
    expect(nextTrackIndex(2, 3)).toBe(0); // wraps
    expect(nextTrackIndex(0, 0)).toBe(0); // empty playlist safe
  });

  it("ambient player starts at the first track and advances/wraps on 'ended'", () => {
    render(
      <AudioProvider>
        <AudioConsumer />
      </AudioProvider>,
    );

    const audio = screen.getByTestId("ambient-audio") as HTMLAudioElement;
    expect(audio.src).toContain("/track-0.wav");

    fireEvent(audio, new Event("ended"));
    expect(audio.src).toContain("/track-1.wav");

    fireEvent(audio, new Event("ended"));
    expect(audio.src).toContain("/track-2.wav");

    // Wrap back to the first track after the last.
    fireEvent(audio, new Event("ended"));
    expect(audio.src).toContain("/track-0.wav");
  });

  it("toggleMute flips state, persists to localStorage, and reflects on the element", () => {
    render(
      <AudioProvider>
        <AudioConsumer />
      </AudioProvider>,
    );

    const audio = screen.getByTestId("ambient-audio") as HTMLAudioElement;
    expect(screen.getByTestId("muted")).toHaveTextContent("false");
    expect(audio.muted).toBe(false);

    fireEvent.click(screen.getByText("toggle"));

    expect(screen.getByTestId("muted")).toHaveTextContent("true");
    expect(localStorage.getItem("nl-audio-muted")).toBe("true");
    expect(audio.muted).toBe(true);
  });

  it("playMoveSound plays the mapped effect and respects volume", () => {
    render(
      <AudioProvider>
        <AudioConsumer />
      </AudioProvider>,
    );

    fireEvent.click(screen.getByText("attack"));
    expect(MockAudio.instances).toHaveLength(1);
    expect(MockAudio.instances[0].src).toBe("/attack.wav");
    expect(MockAudio.instances[0].volume).toBe(0.4); // default volume
    expect(MockAudio.instances[0].play).toHaveBeenCalled();

    fireEvent.click(screen.getByText("defend"));
    expect(MockAudio.instances[1].src).toBe("/block.wav");

    fireEvent.click(screen.getByText("ability"));
    expect(MockAudio.instances[2].src).toBe("/ability.wav");

    fireEvent.click(screen.getByText("ultimate"));
    expect(MockAudio.instances[3].src).toBe("/ultimate.wav");
  });

  it("playMoveSound is silent (creates no audio) while muted", () => {
    render(
      <AudioProvider>
        <AudioConsumer />
      </AudioProvider>,
    );

    fireEvent.click(screen.getByText("toggle")); // mute
    MockAudio.instances = [];

    fireEvent.click(screen.getByText("attack"));
    expect(MockAudio.instances).toHaveLength(0);
  });
});
