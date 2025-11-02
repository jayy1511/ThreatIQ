from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import auth, analyze, stats

app = FastAPI(title="ThreatIQ API")

# TEMP: permissive CORS to debug
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # open to all origins
    allow_credentials=False,      # must be False when allow_origins=["*"]
    allow_methods=["*"],          # allow POST/GET/OPTIONS/etc.
    allow_headers=["*"],          # allow auth/content-type headers
)

app.include_router(auth.router)
app.include_router(analyze.router)
app.include_router(stats.router)

@app.get("/health")
def health():
    return {"status": "ok"}
