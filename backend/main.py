import os
import logging

from dotenv import load_dotenv

# Load backend/.env before anything below reads os.environ (e.g. CORS_ORIGINS).
# Other modules also call load_dotenv() as a side effect of being imported, but
# relying on that import order is fragile — main.py loads its own env vars
# directly, before the `routers` import below.
load_dotenv()

# Configure logging for timing instrumentation and debugging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import battle, data, digitize

app = FastAPI(title="Nine Lives API", version="0.1.0")

origins_str = os.getenv("CORS_ORIGINS", "http://localhost:5173")
origins = [o.strip() for o in origins_str.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
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
