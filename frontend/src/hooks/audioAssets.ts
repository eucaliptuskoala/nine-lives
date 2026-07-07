/**
 * Static audio asset resolution via Vite `import.meta.glob`.
 *
 * Both globs are eager + `?url` so the bundler emits the files and hands us
 * their final URLs at build time. Dropping new files into the asset folders is
 * picked up automatically with no code change:
 *
 * - `src/assets/ambient/*` — a GROWABLE background-music playlist.
 * - `src/assets/sounds/*`  — per-move sound effects, keyed by base filename.
 *
 * This module is intentionally tiny and side-effect free so tests can `vi.mock`
 * it to supply a deterministic playlist / effect map.
 */

const ambientModules = import.meta.glob("../assets/ambient/*.{wav,mp3,ogg}", {
  eager: true,
  query: "?url",
  import: "default",
});

/** Stable, alphabetically-ordered list of ambient track URLs. */
export const AMBIENT_TRACKS: string[] = Object.keys(ambientModules)
  .sort()
  .map((key) => ambientModules[key] as string);

const soundModules = import.meta.glob("../assets/sounds/*.{wav,mp3,ogg}", {
  eager: true,
  query: "?url",
  import: "default",
});

/** Map of sound-effect base filename (e.g. "attack_sound") → URL. */
export const SOUND_EFFECTS: Record<string, string> = Object.entries(
  soundModules,
).reduce<Record<string, string>>((acc, [path, url]) => {
  const base = path.split("/").pop()?.replace(/\.[^.]+$/, "") ?? path;
  acc[base] = url as string;
  return acc;
}, {});

/** Player-move kinds that map to a sound effect. */
export type MoveSoundKind = "attack" | "defend" | "ability" | "ultimate";

/** Move kind → effect base filename. */
export const MOVE_SOUND_MAP: Record<MoveSoundKind, string> = {
  attack: "attack_sound",
  defend: "block_sound",
  ability: "ability_sound",
  ultimate: "ultimate_sound",
};
