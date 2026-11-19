# 分機通訊錄（一廠）

依 `extdir-docs`（需求文件、列印規則分析、EC Portal 架構文件）實作的第一階段系統：
FastAPI + Postgres，登入走 authentik（OIDC），部署在 Synology NAS 的 Docker。

| 路由 | 對象 | 內容 |
|---|---|---|
| `/` 與 `/api/public/search` | 內網任何人（免登入） | 查詢；**固定只回傳**姓名、部門、職稱、分機、等級；每 IP 限流 |
| `/admin/*` | 一廠廠務（群組 `Portal-Dir-Admins`） | 異動收件匣、人員與單位、部門表、分機號碼表、列印與匯出、異動紀錄 |
| `/api/internal/*` | n8n（密鑰） | Domino 每日比對、彙整信內容（見 `deploy/n8n-contract.md`） |
| `/auth/*` | | OIDC 登入、登出 |

## 本機開發

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
pytest                                   # SQLite 記憶體，約 5 秒
ruff check .
```

用真的 Postgres 跑測試：`TEST_DATABASE_URL=postgresql+psycopg2://… pytest`。

啟動（開發模式，假登入）：

```bash
export AUTH_MODE=dev DATABASE_URL=sqlite:///./extdir.db
alembic upgrade head && python -m app.cli seed-plant1
uvicorn app.main:app --port 8002        # /auth/dev-login 以假帳號登入
```

## 已驗證與未驗證

**已驗證（自動化測試 54＋5 項，SQLite 與 Postgres 16 都通過；另在 Postgres 上用瀏覽器走過一遍）**

- 貼牆版排版與廠務提供的貼牆表（`tests/fixtures/plant1-wall.xlsx`）**逐列一致**：標題、名稱、分機、等級、空號、合併、順序。
- Domino 比對規則表（新進、離職、調部門、升遷、部門改名、f＋數字、異常暫停、還原）。
- 維護規則（只停用不刪除、同名同分機才算重複、移動擋同名、不能停用有人的部門、號段提醒…）。
- 公開查詢欄位白名單與限流、維護頁授權（無群組 403）、所有 POST 的 CSRF、內部 API 密鑰、production 啟動安全檢查。
- OIDC：以**假的** authentik 回應驗證「收到 token 之後」的行為。

**未驗證（需要在 NAS 現場做）**

1. **Docker 映像**：開發環境沒有 Docker 服務，`Dockerfile`、`docker-compose.nas.yml` 沒有實際建置過。
2. **真的 authentik**：discovery、Redirect URI、`groups` claim 是否真的帶在 userinfo 裡（見下方現場驗證清單 3）。
3. **n8n 與 Domino**：兩個 workflow 尚未建立（見 `deploy/n8n-contract.md`）。
4. **Excel 實際列印**：只驗證檔案結構（A4 直式、80%、合併儲存格、字型），沒有真的印出來比對一頁放得下。
5. 手機版面、瀏覽器相容性只在桌面 Chromium 看過。

## 尚未做（需求文件有、這版沒有）

- **列印版 2（新風格卡片，橫式／直式）**：需求 7.3，未實作；貼牆版與 EIP 已完成。
- **每日彙整信的寄送**、鈴鐺通知：只提供 digest API。
- **第二階段（二、三、四廠、台北）**：資料模型已帶廠區欄位，但畫面與權限目前固定一廠（`DEFAULT_PLANT`）。
- 需求第 9 節的待確認事項仍未解決（廠務名單、Domino 工號／職稱 API、貼牆表沒印課長的課…），其中**職稱沒開出來時主管判斷無法運作**。
- 貼牆版目前只有 HTML 預覽與 Excel 下載，沒有「旁邊即時預覽、可拖曳分欄」的互動介面；分欄在部門表頁設定。

## 部署到 NAS（步驟比照 EC Portal 05 指南，埠與名稱已避開 EC Portal）

| 項目 | 值 |
|---|---|
| 資料夾 | `/volume1/docker/extdir-web/` |
| 容器埠 / DSM 反向代理 | `8002` → `https://10.11.1.40:8445` |
| compose 專案 / 映像 | `extdir-web` / `extdir-app:nas` |
| session cookie | `extdir_session`（EC Portal 用預設的 `session`，不可相同） |
| 資料庫 / 帳號 | `extdir` / `extdir_app`（Postgres 埠 5433） |
| authentik 應用 / client id | slug `extdir` / `extdir` |
| 群組 | `Portal-Dir-Admins`（可再設 `Portal-Dir-*` 其他角色） |

1. **B 資料庫**：在 NAS Postgres 建 `extdir` 與 `extdir_app`（密碼自己產生保管）。
2. **C authentik**：新增 OAuth2/OIDC provider 與應用 `extdir`；Redirect URI = `https://10.11.1.40:8445/auth/callback`；建群組 `Portal-Dir-Admins`；
   **進入條件**只放行 `Portal-Dir-` 群組（`any(g.name.startswith("Portal-Dir-") for g in request.user.groups.all())`），不要照抄 EC 的 `startswith("Portal-")`；
   確認 userinfo 會帶出 `groups`。
3. **D 部署**：上傳整個資料夾，`cp deploy/.env.example deploy/.env` 填值（`chmod 600`），然後
   ```bash
   cd deploy
   sudo docker compose -f docker-compose.nas.yml build
   sudo docker compose -f docker-compose.nas.yml run --rm portal alembic upgrade head
   sudo docker compose -f docker-compose.nas.yml run --rm portal python -m app.cli seed-plant1
   sudo docker compose -f docker-compose.nas.yml up -d
   curl http://127.0.0.1:8002/healthz
   ```
   **打包前確認** `app/static/`、`app/templates/`、`seed/`、`migrations/` 都在（EC Portal 就曾因打包漏掉 static 檔案出事）。
4. **E DSM 反向代理**：來源 HTTPS `10.11.1.40:8445` → 目的地 HTTP `localhost:8002`，憑證沿用 EC Portal 那張。
   **DSM 防火牆請限制 8002 只給本機與 n8n**：`TRUST_PROXY=true` 時限流會信任 `X-Forwarded-For`，若使用者能直連 8002 就能偽造來源 IP 繞過限流。
5. 備份：`extdir` 資料庫、`deploy/.env` 要納入 NAS 備份。

### 現場驗證清單

| # | 案例 | 預期 |
|---|---|---|
| 1 | 沒登入開 `https://10.11.1.40:8445/` 搜尋 | 可查，只有五個欄位，沒有編輯記號、沒有 Email |
| 2 | 沒登入開 `/admin/` | 導向 authentik 登入 |
| 3 | 有 `Portal-Dir-Admins` 的人登入 | 進入收件匣；若一律 403，多半是 `groups` claim 沒帶出，或加入群組前就登入過（要登出再登入） |
| 4 | 只有 `Portal-ECQuery-*` 群組的人 | authentik 就擋下（進入條件） |
| 5 | 沒任何 `Portal-*` 群組的人 | authentik 擋下 |
| 6 | **同一個瀏覽器**先開 EC Portal、再開本站，來回切換 | 都不用重新登入（驗證 cookie 名稱已分開） |
| 7 | 新增一筆單位、停用、再啟用 | 公開查詢頁即時反映；異動紀錄有記錄 |
| 8 | 下載貼牆版 Excel，用 Excel 開啟並列印預覽 | A4 直式、一頁放完，與牆上現行版面一致 |
| 9 | 部署後 EC Portal 首頁與查詢 | 仍正常（驗證沒影響到現有容器） |
| 10 | 登出後再開 `/admin/` | 要求重新登入 |
