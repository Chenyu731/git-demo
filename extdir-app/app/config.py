"""設定：全部由環境變數讀取（見 deploy/.env.example）。密碼與密鑰不進 repo。"""
from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # production 時會做啟動安全檢查；dev/test 允許假登入
    app_env: str = "dev"
    database_url: str = "sqlite:///./extdir.db"
    session_secret: str = "dev-only-change-me"
    # 與 EC Portal 的 cookie（預設名 session）分開，兩站同為 10.11.1.40，瀏覽器 cookie 不分埠
    session_cookie: str = "extdir_session"
    public_base_url: str = "http://localhost:8002"

    # authentik（OIDC）。issuer 結尾要有斜線，與 token 的 iss 相同
    auth_mode: str = "oidc"  # oidc | dev
    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""

    # 維護權限：廠區代號 -> authentik 群組（程式不寫死群組名）
    plant_admin_groups: dict[str, str] = Field(default_factory=lambda: {"1": "Portal-Dir-Admins"})

    # n8n 與本系統之間的密鑰（n8n 呼叫 /api/internal/*）
    internal_api_secret: str = ""
    n8n_export_webhook: str = ""

    # 公開查詢限流：每個 IP 每分鐘次數
    public_rate_limit_per_min: int = 60
    # 在 DSM 反向代理後面時設 true，才信任 X-Forwarded-For 取得真實 IP（否則所有人共用一個限流桶）
    trust_proxy: bool = False

    # Domino 比對保護（需求 5.5）
    domino_leave_abs_limit: int = 5
    domino_leave_ratio_limit: float = 0.03

    default_plant: str = "1"


@lru_cache
def get_settings() -> Settings:
    return Settings()


def check_startup_safety(s: Settings) -> None:
    """production 禁止不安全設定，寧可啟動失敗。"""
    if s.app_env != "production":
        return
    problems = []
    if s.auth_mode != "oidc":
        problems.append("production 必須 AUTH_MODE=oidc")
    if s.session_secret in ("", "dev-only-change-me") or len(s.session_secret) < 32:
        problems.append("SESSION_SECRET 必須設定且至少 32 字元")
    if not (s.oidc_issuer and s.oidc_client_id and s.oidc_client_secret):
        problems.append("OIDC_ISSUER / OIDC_CLIENT_ID / OIDC_CLIENT_SECRET 必須設定")
    if not s.oidc_issuer.endswith("/"):
        problems.append("OIDC_ISSUER 結尾必須有斜線")
    if len(s.internal_api_secret) < 16:
        problems.append("INTERNAL_API_SECRET 必須設定且至少 16 字元")
    if problems:
        raise RuntimeError("啟動安全檢查失敗：" + "；".join(problems))
