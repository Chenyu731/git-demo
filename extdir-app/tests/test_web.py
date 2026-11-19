import pytest

from app import ratelimit
from app.config import Settings, check_startup_safety

from .conftest import csrf_of


def test_public_search_needs_no_login_and_only_five_fields(client):
    r = client.get("/api/public/search?q=陳文斌")
    assert r.status_code == 200
    rows = r.json()["rows"]
    assert rows and set(rows[0]) == {"name", "dept", "title", "ext", "grade"}  # 不含 email 等其他欄位
    assert rows[0]["ext"] == 320 and rows[0]["grade"] == "A"


def test_public_search_by_ext_and_dept_filter(client):
    assert len(client.get("/api/public/search?q=211").json()["rows"]) == 2  # 製一組、製二組
    top = client.get("/api/public/search").json()["depts"]
    pb = next(d for d in top if d["name"] == "品保部")
    names = {r["dept"].split(" › ")[0] for r in client.get(f"/api/public/search?dept={pb['id']}").json()["rows"]}
    assert names == {"品保部"}


def test_public_rate_limit(client, monkeypatch):
    monkeypatch.setattr("app.ratelimit.get_settings", lambda: Settings(public_rate_limit_per_min=3))
    ratelimit.reset()
    codes = [client.get("/api/public/search").status_code for _ in range(5)]
    assert codes == [200, 200, 200, 429, 429]


def test_public_page_has_no_edit_links(client):
    r = client.get("/")
    assert r.status_code == 200 and "/admin" not in r.text.replace("廠務登入", "")


def test_admin_requires_login(client):
    r = client.get("/admin/")
    assert r.status_code == 303 and r.headers["location"] == "/auth/login"


def test_admin_requires_plant_admin_group(client):
    client.get("/auth/dev-login?email=x@example.com&groups=Portal-ECQuery-Users")
    assert client.get("/admin/people", headers={"accept": "application/json"}).status_code == 403


def test_admin_ok_for_group(admin):
    for path in ("/admin/", "/admin/people", "/admin/depts", "/admin/exts", "/admin/print", "/admin/audit"):
        assert admin.get(path).status_code == 200, path


def test_post_requires_csrf(admin):
    r = admin.post("/admin/people/save", data={"type": "U", "name": "測試", "ext": "999"})
    assert r.status_code == 403
    tok = csrf_of(admin)
    r = admin.post("/admin/people/save", data={"type": "U", "name": "測試單位", "ext": "999", "csrf_token": tok,
                                                "in_directory": "1"})
    assert r.status_code == 303 and "err=" not in r.headers["location"]
    assert any(x["name"] == "測試單位" for x in admin.get("/api/public/search?q=測試單位").json()["rows"])


def test_export_downloads(admin):
    tok = csrf_of(admin)
    for kind in ("eip", "wall"):
        r = admin.post(f"/admin/export/{kind}", data={"csrf_token": tok})
        assert r.status_code == 200 and r.content[:2] == b"PK"  # xlsx 是 zip
    assert admin.post("/admin/export/eip", data={}).status_code == 403


def test_logout_clears_session(admin):
    tok = csrf_of(admin)
    admin.post("/auth/logout", data={"csrf_token": tok})
    assert admin.get("/admin/").status_code == 303


def test_dev_login_disabled_in_production(client):
    from app.config import get_settings
    client.app.dependency_overrides[get_settings] = lambda: Settings(auth_mode="oidc", app_env="production")
    assert client.get("/auth/dev-login").status_code == 404


def test_internal_api_secret(client):
    body = {"people": [{"email": "a@x.com", "name": "甲"}], "baseline": True}
    assert client.post("/api/internal/domino-sync", json=body).status_code == 403
    assert client.post("/api/internal/domino-sync", json=body, headers={"x-internal-secret": "wrong"}).status_code == 403
    r = client.post("/api/internal/domino-sync", json=body, headers={"x-internal-secret": "s" * 20})
    assert r.status_code == 200 and r.json()["baseline"] is True


def test_production_startup_safety():
    with pytest.raises(RuntimeError, match="啟動安全檢查失敗"):
        check_startup_safety(Settings(app_env="production", auth_mode="dev"))
    good = Settings(app_env="production", auth_mode="oidc", session_secret="x" * 40, oidc_issuer="https://a/b/",
                    oidc_client_id="c", oidc_client_secret="s", internal_api_secret="y" * 20)
    check_startup_safety(good)
