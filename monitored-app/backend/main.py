import os
import time
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"), format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("monitored-api")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://demo:demo_password@demo-postgres:5432/shop")
engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=2)
REQUESTS = Counter("http_requests_total", "HTTP requests", ["method", "path", "status"])
LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency", ["path"])
FAULT_MODE = "normal"


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE IF NOT EXISTS products (id SERIAL PRIMARY KEY, name TEXT NOT NULL, price NUMERIC(10,2) NOT NULL)"))
            conn.execute(text("CREATE TABLE IF NOT EXISTS orders (id SERIAL PRIMARY KEY, items TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'created', created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())"))
            conn.execute(text("INSERT INTO products (name, price) SELECT 'Demo keyboard', 2999 WHERE NOT EXISTS (SELECT 1 FROM products)"))
    except SQLAlchemyError:
        logger.exception("Database initialization failed")
    yield


app = FastAPI(title="DevOpsPilot Demo Shop API", lifespan=lifespan)
try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
    provider = TracerProvider(resource=Resource.create({"service.name": os.getenv("OTEL_SERVICE_NAME", "monitored-api")}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317"), insecure=True)))
    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(app)
    SQLAlchemyInstrumentor().instrument(engine=engine)
except Exception:
    logger.exception("OpenTelemetry instrumentation unavailable")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.middleware("http")
async def observe(request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    except Exception:
        logger.exception("Unhandled request error", extra={"path": request.url.path})
        raise
    finally:
        elapsed = time.perf_counter() - start
        REQUESTS.labels(request.method, request.url.path, str(status)).inc()
        LATENCY.labels(request.url.path).observe(elapsed)


@app.get("/health")
def health():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected"}
    except SQLAlchemyError as exc:
        logger.exception("Database health check failed")
        raise HTTPException(503, "Database unavailable") from exc


@app.get("/health/database")
def database_health():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "connected"}


@app.get("/products")
def products():
    if FAULT_MODE == "faulty":
        raise HTTPException(500, "Controlled faulty deployment mode")
    if FAULT_MODE == "latency":
        time.sleep(4)
    try:
        with engine.connect() as conn:
            rows = conn.execute(text("SELECT id, name, price FROM products ORDER BY id")).mappings().all()
            return [dict(row) for row in rows]
    except SQLAlchemyError as exc:
        logger.exception("Product query failed; database connection error")
        raise HTTPException(503, "Product database unavailable") from exc


@app.get("/products/{product_id}")
def product(product_id: int):
    with engine.connect() as conn:
        row = conn.execute(text("SELECT id, name, price FROM products WHERE id=:id"), {"id": product_id}).mappings().first()
    if not row:
        raise HTTPException(404, "Product not found")
    return dict(row)


@app.post("/cart")
def update_cart(payload: dict):
    items = payload.get("items", [])
    if not isinstance(items, list) or not items:
        raise HTTPException(422, "Cart requires at least one item")
    return {"items": items, "item_count": len(items), "status": "cart_updated"}


@app.post("/orders")
def create_order(payload: dict):
    import json
    items = payload.get("items")
    if not isinstance(items, list) or not items:
        raise HTTPException(422, "Order requires at least one item")
    try:
        with engine.begin() as conn:
            order_id = conn.execute(text("INSERT INTO orders (items) VALUES (:items) RETURNING id"), {"items": json.dumps(items)}).scalar_one()
        return {"order_id": order_id, "status": "created", "items": items}
    except SQLAlchemyError as exc:
        logger.exception("Order creation failed")
        raise HTTPException(503, "Order database unavailable") from exc


@app.get("/orders/{order_id}")
def get_order(order_id: int):
    with engine.connect() as conn:
        row = conn.execute(text("SELECT id, items, status, created_at FROM orders WHERE id=:id"), {"id": order_id}).mappings().first()
    if not row:
        raise HTTPException(404, "Order not found")
    return dict(row)


@app.post("/payments")
def create_payment(payload: dict):
    order_id = payload.get("order_id")
    if not isinstance(order_id, int):
        raise HTTPException(422, "order_id must be an integer")
    with engine.begin() as conn:
        result = conn.execute(text("UPDATE orders SET status='paid' WHERE id=:id"), {"id": order_id})
        if result.rowcount == 0:
            raise HTTPException(404, "Order not found")
    return {"order_id": order_id, "payment_status": "simulated_success"}


@app.post("/demo/fault")
def set_fault(payload: dict):
    global FAULT_MODE
    mode = payload.get("mode")
    if mode not in {"normal", "latency", "faulty"}:
        raise HTTPException(422, "Unsupported fault mode")
    FAULT_MODE = mode
    logger.warning("Demo fault mode changed", extra={"fault_mode": mode})
    return {"fault_mode": FAULT_MODE}


@app.get("/metrics")
def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
