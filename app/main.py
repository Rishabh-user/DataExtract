"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.api.routes import router as api_router
from app.core.config import get_settings
from app.core.exceptions import AppException
from app.core.logging import get_logger, setup_logging
from app.database.elasticsearch import es_client
from app.database.models import Base
from app.database.session import engine
from app.database.project_session import DATABASES_DIR, dispose_all_engines

settings = get_settings()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)

    # Ensure main admin database tables exist (projects + api_keys)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Main database tables ensured.")

    await es_client.connect()

    Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
    Path("email_logs").mkdir(exist_ok=True)
    DATABASES_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Project databases directory: %s", DATABASES_DIR.resolve())

    logger.info("Application ready at http://%s:%s", settings.HOST, settings.PORT)
    yield

    await es_client.close()
    await dispose_all_engines()
    await engine.dispose()
    logger.info("Shutdown complete.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Extract structured data from PDF, Excel, Word, Email, CSV, PowerPoint, and Images.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")


# ─── Frontend Routes ──────────────────────────────────────────────────────────

@app.get("/login", include_in_schema=False)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/", include_in_schema=False)
async def dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.get("/upload", include_in_schema=False)
async def upload_page(request: Request):
    return templates.TemplateResponse("upload.html", {"request": request})


@app.get("/view/{document_id}", include_in_schema=False)
async def view_document(request: Request, document_id: int):
    return templates.TemplateResponse("view.html", {"request": request, "document_id": document_id})


@app.get("/documents", include_in_schema=False)
async def documents_page(request: Request):
    return templates.TemplateResponse("filter.html", {"request": request})


@app.get("/keys", include_in_schema=False)
async def keys_page(request: Request):
    return templates.TemplateResponse("keys.html", {"request": request})


@app.get("/email", include_in_schema=False)
async def email_page(request: Request):
    return templates.TemplateResponse("email.html", {"request": request})


@app.get("/admin", include_in_schema=False)
async def admin_page(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})


# ─── Exception Handlers ───────────────────────────────────────────────────────

@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.message, "detail": exc.detail},
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception: %s", exc)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error.", "detail": str(exc) if settings.DEBUG else None},
    )
