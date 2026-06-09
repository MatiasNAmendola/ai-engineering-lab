import os
import logging
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .infrastructure.database.db_models import Base, DBCurricularRequirement
from .infrastructure.http.api import router as api_router

# 1. Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("textbook_generator")

# 2. Database Connection (SQLite)
# Store database inside the workspace
DB_PATH = "textbook_generator.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

logger.info(f"Connecting to SQLite Database at: {DATABASE_URL}")
engine = create_engine(
    DATABASE_URL, 
    connect_args={"check_same_thread": False} # Needed for SQLite concurrency in FastAPI
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. Create tables
Base.metadata.create_all(bind=engine)

# 4. FastAPI Setup
app = FastAPI(
    title="Curriculum Textbook Engine",
    description="Clean Architecture textbook generator using PydanticAI",
    version="1.0.0"
)

# 5. Database Session Middleware
@app.middleware("http")
async def db_session_middleware(request: Request, call_next):
    request.state.db = SessionLocal()
    try:
        response = await call_next(request)
    finally:
        request.state.db.close()
    return response

# 6. Include API Routers
app.include_router(api_router, prefix="/api")

# 7. Auto-Seed Database on Startup if empty
@app.on_event("startup")
def startup_event():
    db = SessionLocal()
    try:
        count = db.query(DBCurricularRequirement).count()
        if count == 0:
            logger.info("Database requirements catalog is empty. Seeding initial guidelines...")
            # We call the populate logic
            from .infrastructure.http.api import populate_requirements
            from .infrastructure.database.sqlite_repository import SQLiteRequirementRepository
            repo = SQLiteRequirementRepository(db)
            populate_requirements(repo)
            logger.info("Initial guidelines seeded successfully.")
    except Exception as e:
        logger.exception("Failed to seed curricular guidelines during startup")
    finally:
        db.close()

# 8. Mount Static Web Frontend
# Locate the static folder relative to this main.py file
current_dir = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(current_dir, "static")

# If static files exist, serve them.
# We mount StaticFiles at the root, but to avoid blocking API requests we do it after including routers.
if os.path.exists(static_dir):
    logger.info(f"Mounting static files from: {static_dir}")
    app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
else:
    logger.error(f"Static directory not found at: {static_dir}")
    @app.get("/")
    def read_root():
        return {"message": "API is online, but static assets are missing."}
