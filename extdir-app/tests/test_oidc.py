"""OIDC 流程：用假的 authentik 用戶端驗證本系統「收到 token 之後」的行為。
無法在此測到的部分（真的 authentik 的 discovery、redirect URI、群組 claim 是否有帶出）見 deploy/README.md 的現場驗證清單。"""
import pytest
from fastapi.responses import RedirectResponse

from app.config import Settings, get_settings


class FakeAuthentik:
    def __init__(self, userinfo):
        self.userinfo = userinfo
        self.redirect_uri = None

    async def authorize_redirect(self, request, redirect_uri):
        self.redirect_uri = redirect_uri
        return RedirectResponse("https://authentik.example/authorize", status_code=302)

    async def authorize_access_token(self, request):
        return {"userinfo": self.userinfo}


@pytest.fixture
def oidc(client, monkeypatch):
    client.app.dependency_overrides[get_settings] = lambda: Settings(
        auth_mode="oidc", public_base_url="https://10.11.1.40:8445", oidc_issuer="http://a/", oidc_client_id="c",
        oidc_client_secret="s")

    def install(userinfo):
        fake = FakeAuthentik(userinfo)
        monkeypatch.setattr("app.auth._client", lambda s: fake)
        return fake
    return install


def test_login_redirects_to_authentik_with_public_callback_url(client, oidc):
    fake = oidc({})
    r = client.get("/auth/login")
    assert r.status_code == 302 and r.headers["location"].startswith("https://authentik.example")
    assert fake.redirect_uri == "https://10.11.1.40:8445/auth/callback"  # 要與 authentik 應用的 Redirect URI 一致


def test_callback_admin_group_can_use_admin_pages(client, oidc):
    oidc({"email": "Boss@Example.com", "name": "廠務", "groups": ["Portal-Dir-Admins", "Other"]})
    r = client.get("/auth/callback")
    assert r.status_code == 303 and r.headers["location"] == "/admin/"
    assert client.get("/admin/people").status_code == 200
    assert client.get("/admin/audit").status_code == 200


def test_callback_other_feature_group_is_forbidden(client, oidc):
    oidc({"email": "ec@example.com", "groups": ["Portal-ECQuery-Users"]})  # 只有 EC 查詢群組，不是本站廠務
    client.get("/auth/callback")
    assert client.get("/admin/people", headers={"accept": "application/json"}).status_code == 403


def test_callback_without_email_rejected(client, oidc):
    oidc({"name": "x", "groups": ["Portal-Dir-Admins"]})
    assert client.get("/auth/callback").status_code == 400


def test_dev_login_unavailable_when_oidc(client, oidc):
    oidc({})
    assert client.get("/auth/dev-login").status_code == 404
