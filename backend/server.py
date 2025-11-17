from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth, analyze, stats, chat  # make sure these exist

app = FastAPI(title="ThreatIQ API")

# ---- CORS: allow EVERYTHING in dev so browser stops crying ----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # all origins (localhost, 127.0.0.1, etc.)
    allow_credentials=False,  # must be False when origins="*"
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---- Routers ----
app.include_router(auth.router, prefix="/auth")  # signup/login
app.include_router(analyze.router)               # /analyze, /analyze/history
app.include_router(stats.router)                 # /stats
app.include_router(chat.router)                  # /security-chat


@app.get("/health")
def health():
    return {"status": "ok"}
