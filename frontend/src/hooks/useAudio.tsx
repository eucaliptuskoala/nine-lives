import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";
import {
  AMBIENT_TRACKS,
  MOVE_SOUND_MAP,
  SOUND_EFFECTS,
  type MoveSoundKind,
} from "./audioAssets";

/**
 * Global, app-wide audio state. A SINGLE source of truth for both the ambient
 * background music (see {@link AmbientAudio}) and per-move sound effects
 * (see {@link AudioContextValue.playMoveSound}).
 *
 * Uses the native HTML5 Audio API only — no runtime dependency.
 */
export interface AudioContextValue {
  /** Whether all audio is silenced. Persisted to `localStorage`. */
  muted: boolean;
  /** Flip the mute state (and persist it). */
  toggleMute: () => void;
  /** Master volume in [0, 1]. Persisted to `localStorage`. */
  volume: number;
  /** Set the master volume in [0, 1] (and persist it). */
  setVolume: (v: number) => void;
  /**
   * Play a per-move sound effect. Fire-and-forget: overlapping plays are
   * allowed and any `play()` rejection (autoplay policy) is swallowed so
   * nothing throws and combat flow is never blocked.
   */
  playMoveSound: (kind: MoveSoundKind) => void;
}

const MUTED_KEY = "nl-audio-muted";
const VOLUME_KEY = "nl-audio-volume";
const DEFAULT_VOLUME = 0.4;

/** Safe read from localStorage (never throws in restricted environments). */
function readStorage(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

/** Safe write to localStorage (never throws). */
function writeStorage(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

function readInitialMuted(): boolean {
  return readStorage(MUTED_KEY) === "true";
}

function readInitialVolume(): number {
  const raw = readStorage(VOLUME_KEY);
  if (raw == null) return DEFAULT_VOLUME;
  const parsed = Number.parseFloat(raw);
  if (Number.isNaN(parsed)) return DEFAULT_VOLUME;
  return Math.min(1, Math.max(0, parsed));
}

/**
 * Default no-op audio state used when a component calls {@link useAudio} outside
 * of an {@link AudioProvider}. This keeps the audio layer defensive: a missing
 * provider must never throw or break rendering (existing tests render pages
 * without wrapping them in the provider).
 */
const NOOP_AUDIO: AudioContextValue = {
  muted: false,
  toggleMute: () => {},
  volume: DEFAULT_VOLUME,
  setVolume: () => {},
  playMoveSound: () => {},
};

const AudioContext = createContext<AudioContextValue | undefined>(undefined);

/** Compute the next playlist index, wrapping to 0 after the last track. */
export function nextTrackIndex(current: number, length: number): number {
  if (length <= 0) return 0;
  return (current + 1) % length;
}

/**
 * Long-lived ambient background-music player. Mounted once at the app root so
 * playback persists across route changes.
 *
 * - Plays the {@link AMBIENT_TRACKS} playlist sequentially, advancing on the
 *   `ended` event and wrapping to the first track after the last. A single
 *   track loops itself.
 * - Respects the browser autoplay policy: does NOT autoplay on load. Playback
 *   starts on the first user interaction (pointerdown/keydown) OR when the user
 *   unmutes via the control.
 * - Reflects the shared `muted`/`volume` onto the audio element.
 */
function AmbientAudio({ muted, volume }: { muted: boolean; volume: number }) {
  const tracks = AMBIENT_TRACKS;
  const audioRef = useRef<HTMLAudioElement>(null);
  const startedRef = useRef(false);
  const [index, setIndex] = useState(0);

  const startPlayback = useCallback(() => {
    if (startedRef.current || tracks.length === 0) return;
    startedRef.current = true;
    const el = audioRef.current;
    if (!el) return;
    try {
      const p = el.play();
      if (p && typeof p.then === "function") p.catch(() => {});
    } catch {
      /* autoplay blocked or jsdom — ignore */
    }
  }, [tracks.length]);

  // Reflect volume/mute onto the element; unmuting also kick-starts playback.
  useEffect(() => {
    const el = audioRef.current;
    if (el) {
      el.volume = volume;
      el.muted = muted;
    }
    if (!muted) startPlayback();
  }, [muted, volume, startPlayback]);

  // Point the element at the current track. Continue playback across advances.
  useEffect(() => {
    const el = audioRef.current;
    if (!el || tracks.length === 0) return;
    el.src = tracks[index];
    if (startedRef.current) {
      try {
        const p = el.play();
        if (p && typeof p.then === "function") p.catch(() => {});
      } catch {
        /* ignore */
      }
    }
  }, [index, tracks]);

  // Start on the first user interaction (one-time), honoring autoplay policy.
  useEffect(() => {
    if (tracks.length === 0) return;
    const onInteract = () => startPlayback();
    document.addEventListener("pointerdown", onInteract, { once: true });
    document.addEventListener("keydown", onInteract, { once: true });
    return () => {
      document.removeEventListener("pointerdown", onInteract);
      document.removeEventListener("keydown", onInteract);
    };
  }, [tracks.length, startPlayback]);

  if (tracks.length === 0) return null;

  return (
    <audio
      ref={audioRef}
      data-testid="ambient-audio"
      aria-hidden="true"
      preload="auto"
      // A single track loops itself; multiple tracks advance via `ended`.
      loop={tracks.length === 1}
      onEnded={() => setIndex((i) => nextTrackIndex(i, tracks.length))}
    />
  );
}

/**
 * Provides global audio state to the app and mounts the always-on ambient
 * player. Wrap the app root with this provider (inside/around AuthProvider is
 * fine) so the floating control and ambient player are always mounted.
 */
export function AudioProvider({ children }: { children: ReactNode }) {
  const [muted, setMuted] = useState<boolean>(readInitialMuted);
  const [volume, setVolumeState] = useState<number>(readInitialVolume);

  // Refs mirror the latest values so `playMoveSound` (a stable callback) always
  // reads current state without needing to be re-created.
  const mutedRef = useRef(muted);
  const volumeRef = useRef(volume);
  useEffect(() => {
    mutedRef.current = muted;
  }, [muted]);
  useEffect(() => {
    volumeRef.current = volume;
  }, [volume]);

  const toggleMute = useCallback(() => {
    setMuted((prev) => {
      const next = !prev;
      writeStorage(MUTED_KEY, String(next));
      return next;
    });
  }, []);

  const setVolume = useCallback((v: number) => {
    const clamped = Math.min(1, Math.max(0, v));
    writeStorage(VOLUME_KEY, String(clamped));
    setVolumeState(clamped);
  }, []);

  const playMoveSound = useCallback((kind: MoveSoundKind) => {
    if (mutedRef.current) return;
    const url = SOUND_EFFECTS[MOVE_SOUND_MAP[kind]];
    if (!url) return;
    try {
      // Clone per play (new element) so overlapping effects don't cut each
      // other off. Fire-and-forget; swallow autoplay rejections.
      const el = new Audio(url);
      el.volume = volumeRef.current;
      el.play()?.catch(() => {});
    } catch {
      /* ignore — never block combat flow */
    }
  }, []);

  const value = useMemo<AudioContextValue>(
    () => ({ muted, toggleMute, volume, setVolume, playMoveSound }),
    [muted, toggleMute, volume, setVolume, playMoveSound],
  );

  return (
    <AudioContext.Provider value={value}>
      {children}
      <AmbientAudio muted={muted} volume={volume} />
    </AudioContext.Provider>
  );
}

/**
 * Access the shared audio state. Returns a safe no-op implementation when used
 * outside of an {@link AudioProvider} so callers never throw.
 */
export function useAudio(): AudioContextValue {
  return useContext(AudioContext) ?? NOOP_AUDIO;
}
