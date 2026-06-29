> **Hackathon:** #HackTheKitty by coding.kitty
> **Dates:** June 24 – July 7, 2026
> **Format:** Online, solo
> **Goal:** Certificate + project in portfolio

---

## Concept

A web application where the user takes a photo of their cat — real or from the internet — and turns it into a fighting character card of a roguelike game. If the character dies in battle, it goes to the **Memorial** — a special space where you can visit all the fallen cats. The mechanic is inspired by real pet loss and makes the game emotionally meaningful.

---

## Core MVP Features

### 1. Cat Digitizer (Cat Digitization)

- User uploads cat photo
- **ML model** detects breed (or "mixed / unknown")
- **LLM** generates character fighting card:
    - Name (random or based on breed)
    - Stats: HP, Attack, Defense, Speed, Special Ability
    - Short lore description (1–2 sentences)
    - Visual avatar — generated via image generation API based on breed

### 2. Game Mechanics (Roguelike Core)

- **Turn-based combat**, minimal interface: 3 buttons (Attack / Defend / Special)
- Enemies — random cats with auto-generated cards
- Progression: win → next opponent is harder
- Randomization via seed — each run is unique
- No saves within a run (classic roguelike permadeath)

### 3. Memorial (Memorial Space)

- When character dies, a "Farewell" screen appears
- Cat card is saved to **Memorial** — separate tab/page
- In the memorial: name, death date, win count, avatar, lore description
- Quiet, calm visual style — contrast with battle section
- Optional: user can add personal note to the card

---

## Technical Stack

| Layer | Technology |
|---|---|
| Frontend | React + Vite |
| Styling | Tailwind CSS |
| Backend | Python (FastAPI) |
| ML — breed classification | HuggingFace Inference API |
| LLM — card generation | Anthropic Claude API (claude-haiku for speed) |
| Image generation | Gemini 2.5 Flash |
| Storage | Supabase (Postgres + Auth + Storage) |
| Deployment | Vercel (frontend) + Render (backend) |

---

## Scope Boundaries (what's NOT in MVP)

- Multiplayer
- Character progression between runs
- Custom music / sound (max — one background track from freesound.org)
- Complex narrative and dialogues
- Mobile adaptation (priority is desktop)
- User authentication

---

## Rough Day-by-Day Plan

| Days | Task |
|---|---|
| June 24–25 | Project setup, basic UI, photo upload |
| June 26–27 | ML integration (breed classification) |
| June 28–29 | LLM card generation + image gen |
| June 30 – July 1 | Turn-based combat core |
| July 2–3 | Memorial — UI and save logic |
| July 4–5 | Polishing, bug fixes, visuals |
| July 6 | Video demo + README + final deploy |
| July 7 | Submit |

---

## Hackathon vs Project Evaluation Criteria

| Criterion | How this project covers it |
|---|---|
| **Technical execution** | ML + LLM + image gen + game mechanics — complex tech stack |
| **Innovation** | Digitizing a real cat as a game character — unconventional angle |
| **Relevance to theme** | 100% — cats are central to the entire mechanic |
| **Documentation** | README + architecture diagram + video demo |
| **UX/UI** | Two contrasting spaces: battle vs memorial |
| **Security** | API keys in env, basic validation for uploaded files |

---

## Name Variants

- **Nine Lives** — reference to cats' "nine lives", roguelike permadeath
- **Pawfall** — "paw" + "downfall", fallen cats
- **Meowmorial** — playful, memorable
- **The Last Meow** — emotional, fits the memorial theme well

---

Document created: June 23, 2026
