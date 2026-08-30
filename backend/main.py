from backend.inference.ollama_client import warm_up
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config import settings
from backend.review.approval_router import router as review_router
from backend.utils.logger import get_logger


logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------
# Used for startup/shutdown hooks. V1 doesn't need to eagerly load the
# mock inbox here — approval_router lazily loads it on first request via
# _ensure_loaded(). Keeping startup empty means the server boots instantly
# and errors (e.g. a malformed emails.json) surface on the first real
# request rather than blocking the whole app from starting. This lifespan
# hook is still useful as the place V2 will initialize DB connection pools
# (Supabase) and Redis clients.
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"{settings.APP_NAME} v{settings.APP_VERSION} starting up...")
    logger.info(f"Ollama target: {settings.OLLAMA_BASE_URL} (model={settings.OLLAMA_MODEL})")
    warm_up()
    yield
    logger.info(f"{settings.APP_NAME} shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
# Next.js dev server runs on localhost:3000 by default, FastAPI on 8000.
# Different ports = different origins to the browser, so without this the
# frontend's fetch() calls to /api/* get blocked. Locked to localhost dev
# ports only — tighten/replace with real origins before any deployment.
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)



# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
app.include_router(review_router)


# ---------------------------------------------------------------------------
# Root / health check
# ---------------------------------------------------------------------------
@app.get("/")
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


@app.get("/health")
def health():
    return {"status": "ok"}

