# Retro Cat Avatar — Diffusion Prompt Spec

Canonical prompt guidance for generating **Nine Lives** cat avatars in a consistent
8-bit / 16-bit retro style that matches the game's [8bitcn](https://8bitcn.com) UI.

This document is the single source of truth for the *style* of generated avatars.
The digitization pipeline's **Avatar Generator** (`backend/services/image_generator.py`,
Track B) composes the final image prompt by wrapping the per-cat details from the
**Card Generator** (`image_prompt`, breed, colors, personality, class) with the fixed
**style block** below. Keeping the style block in one place guarantees every cat comes
out visually cohesive.

---

## How it's assembled

```
<STYLE POSITIVE>  +  <PER-CAT SUBJECT>   → sent to the image model as the prompt
<STYLE NEGATIVE>                          → sent as the negative prompt (if supported)
```

- **Stable Diffusion / SDXL / ComfyUI** — use `positive` and `negative` fields directly.
- **Gemini 2.5 Flash Image ("nano banana")** and other prompt-only models — there is no
  separate negative field, so append the negatives as an explicit "Avoid:" clause at the
  end of the single prompt (see *Prompt-only models* below).

Recommended generation parameters: **1:1 aspect ratio**, **512×512** (or 256×256 upscaled
with nearest-neighbor to preserve hard pixel edges), one subject, centered.

---

## Style — Positive Prompt (fixed)

> 8-bit retro pixel art portrait of a cat, 16-bit JRPG character sprite, chunky visible
> square pixels, clean pixel grid, limited cohesive color palette (16–32 colors), bold
> dark outline, flat cel shading with simple dithering, front-facing head-and-shoulders
> portrait, centered composition, single subject, plain flat dark background, crisp hard
> edges, high contrast, game character card art, nostalgic arcade aesthetic.

Notes:
- "head-and-shoulders portrait, centered, single subject, plain flat dark background"
  keeps framing consistent across cats and composites cleanly onto the dark UI card.
- The dark background (near-black / deep slate) matches the app theme; request a solid or
  subtly dithered background, **not** transparent (most diffusion models don't do true
  alpha reliably — the frontend renders it inside a card, so a flat dark bg is fine).

## Style — Negative Prompt (what NOT to make)

> photorealistic, 3d render, realistic fur, smooth gradients, soft focus, blurry,
> anti-aliased edges, high-resolution detail, painterly, watercolor, sketch, line art,
> text, letters, watermark, signature, UI, frame, border, multiple cats, extra limbs,
> deformed anatomy, human, full body, cluttered background, busy background, motion blur,
> jpeg artifacts, noise.

---

## Per-cat Subject Template (variable)

Filled in from the digitized cat's data. Keep it short — the style block does the heavy
lifting; the subject just personalizes it.

```
a {breed} cat named {name}, {colors} fur, {class}-class warrior,
personality: {personality}
```

Field sources:
- `{breed}` — from the breed classifier (e.g. "Siamese", fallback "Domestic Shorthair").
- `{name}` — user-provided cat name (avatars generally shouldn't render text, so the name
  mainly nudges character vibe; the negative prompt suppresses actual lettering).
- `{colors}` — dominant fur colors from the color extractor (hex → nearest color words,
  e.g. "orange and cream", "black and grey tabby").
- `{class}` — STRENGTH → burly/armored vibe, AGILITY → sleek/lean vibe,
  INTELLIGENCE → mystic/scholarly vibe. Map the enum to a short descriptor.
- `{personality}` — the optional user description; when present, fold in 3–8 evocative
  words (brave, grumpy, regal, mischievous...). When absent, omit the clause.

---

## Full Assembled Example

**Subject:** a Siamese cat named "Sir Pounce", cream and seal-brown fur, STRENGTH-class
warrior, personality: proud, battle-hardened, a little grumpy.

**Positive (final prompt):**
> 8-bit retro pixel art portrait of a cat, 16-bit JRPG character sprite, chunky visible
> square pixels, clean pixel grid, limited cohesive color palette (16–32 colors), bold
> dark outline, flat cel shading with simple dithering, front-facing head-and-shoulders
> portrait, centered composition, single subject, plain flat dark background, crisp hard
> edges, high contrast, game character card art, nostalgic arcade aesthetic — a Siamese
> cat, cream and seal-brown fur, a proud battle-hardened slightly grumpy STRENGTH-class
> warrior with a burly armored look.

**Negative:**
> photorealistic, 3d render, realistic fur, smooth gradients, soft focus, blurry,
> anti-aliased edges, painterly, sketch, line art, text, letters, watermark, signature,
> UI, frame, border, multiple cats, extra limbs, deformed anatomy, human, full body,
> cluttered background, motion blur, jpeg artifacts, noise.

---

## Prompt-only models (Gemini 2.5 Flash Image)

Gemini has no negative field. Append the avoid-clause to the single prompt:

> {positive style block} — {per-cat subject}. Style must be true pixel art with hard
> square pixels and a limited palette on a flat dark background. Avoid: photorealism,
> 3d, smooth gradients, anti-aliasing, blur, text or watermarks, borders/frames,
> multiple cats, human features, full body, busy backgrounds.

---

## Class → look mapping (reference)

| Class | Visual descriptor to inject |
|---|---|
| STRENGTH | burly, armored, scarred, heavy-set, warrior |
| AGILITY | sleek, lean, alert, quick, scout/ranger |
| INTELLIGENCE | mystic, scholarly, glowing eyes, arcane, robed |

---

## Notes / caveats

- Small pixel-art via diffusion can drift toward "smooth illustration that looks
  pixel-ish." The negatives (`anti-aliased edges`, `smooth gradients`, `high-resolution
  detail`) fight that; generating small (e.g. 256²) then nearest-neighbor upscaling also
  helps preserve hard pixels.
- Keep the **style block byte-for-byte identical** across cats — only the per-cat subject
  changes — so the memorial and battle screens feel like one cohesive set.
- This doc is design guidance for Track B; the exact wiring (where the wrapper is applied)
  lives in `backend/services/image_generator.py` once the ML pipeline is implemented.
