from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import auth, analyze, stats

app = FastAPI(title="ThreatIQ API")

# CORS to allow Next.js frontend on port 3000
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",   # Next.js frontend
        "http://127.0.0.1:3000"    # alias
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router)
app.include_router(analyze.router)
app.include_router(stats.router)

# Health check endpoint
@app.get("/health")
def health():
    return {"status": "ok"}
