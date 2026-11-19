from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from collections import defaultdict, deque
from time import monotonic
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.db.session import Base, engine, SessionLocal
from app import models  # noqa: F401
from app.models import Application, Service
from app.api.routes import auth, applications, incidents, platform, alerts, reports



@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        demo = (
            db.query(Application)
            .filter(Application.name == "DevOpsPilot Demo Shop")
            .first()
        )

        if not demo:
            demo = Application(
                name="DevOpsPilot Demo Shop",
                description="Instrumented e-commerce application monitored by DevOpsPilot AI",
                environment="local-demo",
                health_url="http://monitored-api:8001/health",
            )
            db.add(demo)
            db.flush()

            db.add_all([
                Service(
                    application_id=demo.id,
                    name="monitored-api",
                    service_type="api",
                    container_name="monitored-api",
                    health_url="http://monitored-api:8001/health",
                ),
                Service(
                    application_id=demo.id,
                    name="demo-postgres",
                    service_type="database",
                    container_name="demo-postgres",
                ),
            ])
            db.commit()
    finally:
        db.close()

    app.state.checkpointer = None

    if settings.database_url.startswith("postgresql"):
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        checkpoint_url = settings.database_url.replace(
            "postgresql+psycopg://",
            "postgresql://",
            1,
        )

        async with AsyncPostgresSaver.from_conn_string(
            checkpoint_url
        ) as checkpointer:
            await checkpointer.setup()
            app.state.checkpointer = checkpointer

            print("DevOpsPilot: PostgreSQL LangGraph checkpointer initialized.")

            try:
                yield
            finally:
                app.state.checkpointer = None
    else:
        yield



app = FastAPI(title=settings.app_name, version="1.0.0", description="Evidence-first agentic incident investigation and controlled remediation.", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth.router)
app.include_router(applications.router)
app.include_router(incidents.router)
app.include_router(platform.router)
app.include_router(alerts.router)
app.include_router(reports.router)

# Small single-process guard for the local demo. Use a shared Redis limiter for multi-worker deployment.
_auth_attempts: dict[str, deque[float]] = defaultdict(deque)


@app.middleware("http")
async def auth_rate_limit(request, call_next):
    if request.url.path in {"/api/auth/login", "/api/auth/register"}:
        client_ip = request.client.host if request.client else "unknown"
        bucket = _auth_attempts[client_ip]
        now = monotonic()
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= 10:
            return JSONResponse(status_code=429, content={"detail": "Too many authentication attempts. Try again in a minute."})
        bucket.append(now)
    return await call_next(request)


@app.get("/health")
def health():
    return {"status": "healthy", "service": "devopspilot-api"}
