import os

os.environ.update(APP_ENV="test", AUTH_MODE="dev", DATABASE_URL="sqlite://", SESSION_SECRET="t" * 40,
                  INTERNAL_API_SECRET="s" * 20, PUBLIC_RATE_LIMIT_PER_MIN="1000")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models, ratelimit  # noqa: E402,F401
from app.config import get_settings  # noqa: E402
from app.db import Base, get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.seed import seed_plant1  # noqa: E402


@pytest.fixture
def engine():
    """預設用 SQLite 記憶體；設 TEST_DATABASE_URL 可改用真的 Postgres（每個測試重建資料表）。"""
    url = os.environ.get("TEST_DATABASE_URL")
    if url:
        from sqlalchemy import create_engine
        e = create_engine(url)
        Base.metadata.drop_all(e)
    else:
        from sqlalchemy import create_engine
        e = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(e)
    yield e
    e.dispose()


@pytest.fixture
def db(engine):
    s = sessionmaker(bind=engine, expire_on_commit=False)()
    seed_plant1(s)
    yield s
    s.close()


@pytest.fixture
def plant(db):
    return db.query(models.Plant).one()


@pytest.fixture
def client(engine, db):
    ratelimit.reset()
    app = create_app()
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    def _db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = _db
    return TestClient(app, follow_redirects=False)


@pytest.fixture
def admin(client):
    client.get("/auth/dev-login?email=gm@example.com&groups=Portal-Dir-Admins")
    return client


def csrf_of(client) -> str:
    """從維護頁取得 CSRF token。"""
    import re
    html = client.get("/admin/people/new").text
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def settings():
    return get_settings()
