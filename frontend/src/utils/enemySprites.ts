/**
 * Static enemy sprite resolution via Vite `import.meta.glob`.
 *
 * Mirrors the pattern in `hooks/audioAssets.ts`: eager + `?url` so the bundler
 * emits the files and hands us their final URLs at build time. Dropping a new
 * sprite into `src/assets/enemies/` is picked up automatically with no code
 * change, keyed by the lowercased base filename (e.g. "shadow", "luna").
 *
 * Not every name in the backend's `ENEMY_NAMES` pool has generated art yet
 * (e.g. "Felix" at the time of writing) — `getEnemySpriteUrl` returns
 * `undefined` for any unmatched name so callers can fall back gracefully
 * (see `CatCard`'s emoji fallback) rather than throwing or warning loudly.
 */

const enemySpriteModules = import.meta.glob(
  "../assets/enemies/*.{jpeg,jpg,png,webp}",
  {
    eager: true,
    query: "?url",
    import: "default",
  },
);

/** Map of enemy name (lowercased, e.g. "shadow") → sprite URL. */
export const ENEMY_SPRITES: Record<string, string> = Object.entries(
  enemySpriteModules,
).reduce<Record<string, string>>((acc, [path, url]) => {
  const base = path.split("/").pop()?.replace(/\.[^.]+$/, "") ?? path;
  acc[base.toLowerCase()] = url as string;
  return acc;
}, {});

/**
 * Resolve the bundled sprite URL for an enemy by name (case-insensitive).
 * Returns `undefined` when no matching sprite has been generated yet.
 */
export function getEnemySpriteUrl(name: string): string | undefined {
  return ENEMY_SPRITES[name.toLowerCase()];
}
