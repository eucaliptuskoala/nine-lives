# Procedural Enemy SVG Generation

> **Status:** Future idea (post-MVP)
> **Saved:** June 25, 2026

## Why

Pre-made SVGs work for MVP, but procedural generation gives every enemy a unique look without asset management. Stronger for the "innovation" judging criterion.

## Approach

Generate a unique cat silhouette SVG from a seed (the enemy's name hash).

### What varies

```
Seed (name hash)
  ├── Head shape       → round, triangular, wide
  ├── Ear type         → pointed, folded, tufted
  ├── Eye shape        → round, slit, wide
  ├── Tail             → long, short, curled, bushy
  ├── Body size        → lean, chunky, muscular
  ├── Fur pattern      → stripes, spots, solid, tortie
  ├── Color palette    → derived from round number or random
  └── Pose             → sitting, standing, pouncing
```

### Implementation (rough)

A single function `generateEnemySvg(seed: string): string` that:

1. Seeds a PRNG (e.g. `mulberry32`) from the name hash
2. Picks shape variants using the seeded RNG
3. Renders an `<svg>` with basic `<path>`, `<circle>`, `<ellipse>` elements
4. Returns the SVG string

### Example output

```svg
<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg">
  <!-- body -->
  <ellipse cx="50" cy="65" rx="20" ry="25" fill="#4a4a4a"/>
  <!-- head -->
  <circle cx="50" cy="30" r="15" fill="#4a4a4a"/>
  <!-- ears -->
  <polygon points="38,20 35,5 45,15" fill="#4a4a4a"/>
  <polygon points="62,20 65,5 55,15" fill="#4a4a4a"/>
  <!-- eyes -->
  <circle cx="44" cy="28" r="2" fill="#ff0"/>
  <circle cx="56" cy="28" r="2" fill="#ff0"/>
  <!-- tail -->
  <path d="M30 75 Q10 70 15 50" stroke="#4a4a4a" stroke-width="4" fill="none"/>
</svg>
```

### Integration

Replace `enemyGen.ts` — instead of `avatar_url` pointing to a static asset, call the procedural generator and embed the SVG inline or serve it as a data URI.

### References

- [game-icons.net](https://game-icons.net) — inspiration for silhouette styles
- [svg-path-editor](https://yqnn.github.io/svg-path-editor/) — for designing base paths
