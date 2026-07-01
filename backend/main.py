from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import battle, data, digitize

app = FastAPI(title="Nine Lives API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(digitize.router, prefix="/api")
app.include_router(battle.router, prefix="/api")
app.include_router(data.router, prefix="/api")

@app.get("/api/health")
async def health():
    return {"status": "ok"}
