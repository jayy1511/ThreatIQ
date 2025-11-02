from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import auth, analyze, stats

app = FastAPI(title="ThreatIQ API")

app.add_middleware(
    CORSMiddleware,
    # Exact local dev origins
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    # ✅ Allow any *.vercel.app preview/prod URL
    allow_origin_regex=r"https://.*\.vercel\.app$",
    allow_credentials=True,           # keep if you plan to use cookies; okay with regex
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(analyze.router)
app.include_router(stats.router)

@app.get("/health")
def health():
    return {"status": "ok"}
