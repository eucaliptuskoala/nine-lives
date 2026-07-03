# Overworld backgrounds

Drop fullscreen background images for the Overworld here (e.g. `overworld.png`,
`overworld.jpg`, `.jpeg`, or `.webp`).

`OverworldPage` picks up the first matching image automatically via Vite's
`import.meta.glob`, so no code change is needed after adding one. Until an image
is present the page falls back to a solid retro background color, so a missing
image never breaks the build.

Recommended: a 16-bit / pixel-art scene that matches the retro theme (see
`docs/retro-avatar-prompt.md` for the shared visual style).
