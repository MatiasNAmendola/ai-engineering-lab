import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .infrastructure.database.db_models import Base, DBCurricularRequirement
from .infrastructure.http.api import router as api_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("textbook_generator")

DB_PATH = os.environ.get("TEXTBOOK_DB_PATH", "textbook_generator.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

logger.info(f"Connecting to SQLite Database at: {DATABASE_URL}")
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    db = SessionLocal()
    try:
        count = db.query(DBCurricularRequirement).count()
        if count == 0:
            logger.info("Database requirements catalog is empty. Seeding initial guidelines...")
            from .infrastructure.http.api import populate_requirements
            from .infrastructure.database.sqlite_repository import SQLiteRequirementRepository
            repo = SQLiteRequirementRepository(db)
            populate_requirements(repo)
            logger.info("Initial guidelines seeded successfully.")
    except Exception:
        logger.exception("Failed to seed curricular guidelines during startup")
    finally:
        db.close()
    yield


app = FastAPI(
    title="Curriculum Textbook Engine",
    description="Clean Architecture textbook generator using PydanticAI with NEM/SEP alignment",
    version="2.0.0",
    lifespan=lifespan
)


@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    request.state.db = SessionLocal()
    try:
        response = await call_next(request)
    finally:
        request.state.db.close()
    return response


app.include_router(api_router, prefix="/api")

current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")

if os.path.exists(static_dir):
    logger.info(f"Mounting static files from: {static_dir}")
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
else:
    logger.error(f"Static directory not found at: {static_dir}")

    @app.get("/")
    def read_root():
        return {"message": "API is online, but static assets are missing."}
