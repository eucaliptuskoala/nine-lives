# Nine Lives

Upload a photo of your cat — it gets digitized into a playable roguelike character. Nine lives. When they're gone, they move to the Memorial.

Built for [#HackTheKitty](https://coding.kitty) (June 24 – July 7, 2026).

## Tech Stack

| Layer | Tech |
|-------|------|
| Frontend | React + Vite + TypeScript + Tailwind CSS v3 + framer-motion |
| Backend | Python FastAPI |
| Database + Auth | Supabase |
| Breed classification | HuggingFace Inference API |
| Fur color extraction | OpenCV k-means |
| Name / stats / lore | Claude Haiku (Anthropic) |
| Avatar generation | Gemini 2.5 Flash Image |

## Project Structure

```
nine-lives/
├── frontend/          # React + Vite SPA
├── backend/           # FastAPI server
├── supabase/          # Database migrations
└── docs/              # Planning documents
```

## Local Development

### Frontend

```bash
cd frontend
cp .env.example .env    # fill in your Supabase keys
npm install
npm run dev
```

### Backend

```bash
cd backend
cp .env.example .env    # fill in your API keys
python -m venv venv
source venv/bin/activate
pip install -e .
uvicorn main:app --reload
```

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
