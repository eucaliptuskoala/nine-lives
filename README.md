# Nine Lives

Upload a photo of your cat — it gets digitized into a playable roguelike character. Nine lives. When they're gone, they move to the Memorial.

Built for [#HackTheKitty](https://coding.kitty) (June 24 – July 7, 2026). Ranked 12th out of 127 teams.

> **Note:** The live deployment has been taken offline. To try the game locally, follow the [Local Development](#local-development) instructions below.

## Tech Stack

| Layer                 | Tech                                                         |
| --------------------- | ------------------------------------------------------------ |
| Frontend              | React + Vite + TypeScript + Tailwind CSS v3 + framer-motion  |
| Backend               | Python FastAPI                                               |
| Database + Auth       | Supabase                                                     |
| Breed classification  | Local ViT (HuggingFace Transformers)                         |
| Fur color extraction  | YOLOv11 segmentation + scikit-learn KMeans                   |
| Name / stats / lore   | Gemini 2.5 Flash                                             |
| Avatar generation     | FLUX.1-schnell via HuggingFace Inference Providers           |

## Project Structure

```text
nine-lives/
├── frontend/          # React + Vite SPA
├── backend/           # FastAPI server
├── ml/                # ML pipeline notebooks and utilities
├── supabase/          # Database migrations
└── docs/              # Planning documents
```

## Local Development

### Prerequisites

| Tool | Version | Notes |
|------|---------|-------|
| Node.js | 18+ | `node -v` |
| Python | 3.11+ | `python3 --version` |
| [uv](https://docs.astral.sh/uv/) | latest | `uv` handles Python deps + CPU-only PyTorch wheels automatically |
| Supabase account | free tier | [app.supabase.com](https://app.supabase.com) |

### API Keys

You'll need these before starting — create a Supabase project first, then sign up for the ML services:

| Key | Where to get it | Used by |
|-----|----------------|---------|
| `SUPABASE_URL` | Supabase Dashboard → Settings → API → Project URL | Backend |
| `SUPABASE_SERVICE_KEY` | Same page, under `service_role` (keep secret) | Backend |
| `VITE_SUPABASE_URL` | Same as above | Frontend |
| `VITE_SUPABASE_ANON_KEY` | Same page, under `anon` `public` | Frontend |
| `GEMINI_API_KEY` | [Google AI Studio](https://aistudio.google.com/apikey) | Backend (lore/stats generation) |
| `HUGGINGFACE_API_KEY` | [HuggingFace Settings](https://huggingface.co/settings/tokens) | Backend (avatar generation) |

### 1. Supabase Project

Create a free project and run the schema migrations:

1. Go to [app.supabase.com](https://app.supabase.com), click **New Project**
2. Once created, open **SQL Editor** in the left sidebar
3. Run these three files **in order** (paste contents, click **Run** each time):
   - `supabase/migrations/20250701000000_initial_schema.sql` — tables, indexes, RLS policies
   - `supabase/migrations/20250701000001_storage_setup.sql` — creates the `cat-images` storage bucket + upload/read policies
   - `supabase/migrations/20260702194201_fix_current_round_constraint.sql` — constraint fix
4. Copy your **Project URL**, **anon** key, and **service_role** key from Settings → API

No manual storage bucket setup is needed — the second migration creates and configures it automatically.

> For full schema details see [`supabase/README.md`](supabase/README.md).

### 2. Backend

```bash
cd backend
cp .env.example .env        # paste in Supabase URL, service key, and API keys
uv sync                      # installs all deps (CPU-only PyTorch downloaded automatically)
uv run uvicorn main:app --reload
```

Backend runs on `http://localhost:8000`. Swagger docs at `http://localhost:8000/docs`.

> ML deps (torch, transformers, ultralytics) are ~800 MB on first install. The `pyproject.toml` is configured to pull CPU-only PyTorch wheels — no GPU needed.

### 3. Frontend

```bash
cd frontend
cp .env.example .env        # paste in VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY
npm install
npm run dev
```

Frontend runs on `http://localhost:5173` and proxies API calls to the backend.

### Running Together

Open two terminals — one for the backend, one for the frontend:

```bash
# Terminal 1
cd backend && uv run uvicorn main:app --reload

# Terminal 2
cd frontend && npm run dev
```

Visit `http://localhost:5173` in your browser.

## Security Notes

- **`CORS_ORIGINS` in production:** before going live, set `CORS_ORIGINS` (see
  `backend/.env.example`) to the real deployed frontend origin(s), comma-separated
  if there are multiple. `backend/main.py` defaults `allow_origins` to
  `http://localhost:5173` when this is unset, which is dev-only and must not be
  relied on in a deployed environment. `allow_credentials=True` is enabled, so
  this origin list must stay scoped to origins you actually trust.
- **Token revocation after password reset / sign-out:** this is an accepted
  risk, not a code defect. Supabase access tokens are short-lived, and the
  backend already performs a live `auth.get_user()` check on every request
  (not just local JWT signature validation), which is standard JWT behavior.
  If tighter revocation is needed, shorten the token lifetime in your Supabase
  Auth settings.

## License

MIT
