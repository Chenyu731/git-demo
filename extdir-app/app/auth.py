"""登入（authentik OIDC）、授權、CSRF。

- 公開查詢路由不掛任何檢查；維護路由（/admin/*）一律用 require_admin。
- 授權只看 OIDC 的 groups claim；群組名稱來自設定（plant_admin_groups），程式不寫死。
- 每個 POST 都要 CSRF token。
"""
import hmac
import secrets
from dataclasses import dataclass, field

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from .config import Settings, get_settings

router = APIRouter(prefix="/auth", tags=["auth"])
_oauth: OAuth | None = None


@dataclass
class User:
    email: str
    name: str = ""
    groups: list[str] = field(default_factory=list)

    def is_plant_admin(self, plant_code: str, s: Settings) -> bool:
        g = s.plant_admin_groups.get(plant_code)
        return bool(g) and g in self.groups


def _client(s: Settings):
    global _oauth
    if _oauth is None:
        _oauth = OAuth()
        _oauth.register(
            name="authentik",
            client_id=s.oidc_client_id,
            client_secret=s.oidc_client_secret,
            server_metadata_url=s.oidc_issuer + ".well-known/openid-configuration",
            client_kwargs={"scope": "openid profile email groups"},
        )
    return _oauth.authentik


def session_user(request: Request) -> User | None:
    u = request.session.get("user")
    return User(**u) if u else None


def require_user(request: Request) -> User:
    u = session_user(request)
    if not u:
        # 瀏覽器導向登入；API 呼叫端會看到 401
        raise HTTPException(status_code=401, detail="login required")
    return u


def require_admin(request: Request, s: Settings = Depends(get_settings)) -> User:
    u = require_user(request)
    plant = request.query_params.get("plant") or s.default_plant
    if not u.is_plant_admin(plant, s):
        raise HTTPException(status_code=403, detail="not a plant admin")
    return u


def csrf_token(request: Request) -> str:
    t = request.session.get("csrf")
    if not t:
        t = request.session["csrf"] = secrets.token_urlsafe(32)
    return t


async def verify_csrf(request: Request) -> None:
    sent = request.headers.get("x-csrf-token")
    if not sent:
        form = await request.form()
        sent = form.get("csrf_token")
    expected = request.session.get("csrf", "")
    if not sent or not expected or not hmac.compare_digest(str(sent), expected):
        raise HTTPException(status_code=403, detail="bad csrf token")


@router.get("/login")
async def login(request: Request, s: Settings = Depends(get_settings)):
    if s.auth_mode == "dev":
        return RedirectResponse("/auth/dev-login", status_code=303)
    return await _client(s).authorize_redirect(request, s.public_base_url + "/auth/callback")


@router.get("/callback")
async def callback(request: Request, s: Settings = Depends(get_settings)):
    token = await _client(s).authorize_access_token(request)
    info = token.get("userinfo") or {}
    email = (info.get("email") or "").lower()
    if not email:
        raise HTTPException(400, "OIDC 未提供 email")
    request.session.clear()  # 換 session，避免 session fixation
    request.session["user"] = {"email": email, "name": info.get("name", ""), "groups": list(info.get("groups", []))}
    return RedirectResponse("/admin/", status_code=303)


@router.get("/dev-login")
async def dev_login(request: Request, email: str = "dev@example.com", groups: str = "Portal-Dir-Admins",
                    s: Settings = Depends(get_settings)):
    # 只在 dev/test：production 啟動時已被 check_startup_safety 擋下
    if s.auth_mode != "dev" or s.app_env == "production":
        raise HTTPException(404)
    request.session.clear()
    request.session["user"] = {"email": email, "name": "Dev", "groups": [g for g in groups.split(",") if g]}
    return RedirectResponse("/admin/", status_code=303)


@router.post("/logout", dependencies=[Depends(verify_csrf)])
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)
