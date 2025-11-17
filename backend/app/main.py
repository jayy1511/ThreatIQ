# backend/app/main.py

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routers import auth, analyze, stats, chat  # make sure these router files exist

app = FastAPI(title="ThreatIQ API")

# -------------- CORS (DEV: OPEN TO ALL) --------------
# This completely removes CORS issues in local dev.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],      # allow all origins (localhost, 127.0.0.1, etc.)
    allow_credentials=False,  # MUST be False when allow_origins=["*"]
    allow_methods=["*"],      # allow GET, POST, PUT, DELETE, OPTIONS, ...
    allow_headers=["*"],      # allow all headers (Authorization, Content-Type, ...)
)

# -------------- ROUTERS --------------

# Auth: /auth/...
app.include_router(auth.router, prefix="/auth")

# Analysis: /analyze/... and /analyze/history
app.include_router(analyze.router)

# Stats / dashboard: /stats/...
app.include_router(stats.router)

# Security Chat: /security-chat/...
app.include_router(chat.router)


@app.get("/health")
def health():
    return {"status": "ok"}
