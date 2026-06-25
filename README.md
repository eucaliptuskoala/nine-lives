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

## License

MIT
