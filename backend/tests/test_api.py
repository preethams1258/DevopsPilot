from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db.session import Base, get_db


def test_register_login_and_protected_application_routes():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    try:
        with TestClient(app) as client:
            registered = client.post("/api/auth/register", json={"email": "test@example.com", "full_name": "Test User", "password": "StrongPassword123!"})
            assert registered.status_code == 201
            tokens = registered.json()
            assert tokens["access_token"]
            me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
            assert me.status_code == 200
            assert me.json()["role"] == "admin"
            created = client.post("/api/applications", headers={"Authorization": f"Bearer {tokens['access_token']}"}, json={"name": "Test Shop", "description": "test", "environment": "demo"})
            assert created.status_code == 201
            assert created.json()["name"] == "Test Shop"
            assert client.get("/api/applications").status_code == 401
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(engine)
        engine.dispose()
