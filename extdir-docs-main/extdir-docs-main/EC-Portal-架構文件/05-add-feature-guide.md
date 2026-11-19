# 新增一個內網小功能（獨立網站做法）

給同仁。想做一個新的內網小功能（例如外出單）時看這份。

**關於範例**：目前實際在跑的只有 EC Portal（EC 查詢）。本文的「**外出單（outing）**」是**範例**，用來示範新增第二個獨立網站的每一步，現在並不存在。
實際要做的新功能，請把文中的 `outing` 換成自己的功能名稱（資料夾、資料庫、client id、群組名稱 `Portal-Outing-*`），埠 8001／8444 換成沒人用的埠。

**做法：一個功能一個網站。** 每個功能有自己的網站容器、自己的資料庫、自己的權限群組，彼此不互相干擾；登入（authentik）與 AD 同步則共用現有那一套，不用重做。

> 狀態：這是依 EC Portal 現有的部署與程式整理的做法，**還沒有人實際做過第二個網站**。標「未實測」的地方，第一個照做的人請實測並回頭修正本文。
> 兩個網站的共用程式碼（登入、CSRF、版型…）**第一版先複製**，等第二個網站上線後，再依實際重複的部分討論要不要抽成共用（見第 8 節）。
> 背景與設計理由：`01-architecture.md`。部署細節：`deploy/portal-deploy.md`、`deploy/authentik-deploy.md`。

## 1. 共用什麼、各自什麼

| 項目 | 共用或獨立 | 說明 |
|---|---|---|
| authentik（登入伺服器） | **共用** | 同一台，不重裝；使用者的 AD 帳密、同步、緊急管理員都在這裡 |
| AD 同步 | **共用** | 已經做好 |
| 網站容器 | **各自獨立** | 新的容器、新的連接埠、新的 `.env` |
| 資料庫 | **各自獨立** | NAS Postgres 上新建資料庫與帳號，不碰 `ec_portal` |
| authentik 應用 | **各自獨立** | 在同一台 authentik 新增一個 OIDC 應用（自己的 client id 與 secret） |
| 權限群組 | **各自獨立** | 每個網站自己的群組，例如 `Portal-Outing-Users` |
| 進入條件 | **各自獨立** | 新應用只放行自己的群組，EC 查詢的人進不了 |
| 網址 | **各自獨立** | DSM 反向代理再加一條，例如 `https://10.11.1.40:8444` |
| n8n | 共用同一台 | 每個功能用自己的 webhook 路徑與密鑰 |
| 程式碼 | **先複製，之後再討論共用** | 見第 8 節 |

使用者體驗：同一個瀏覽器已登入 authentik 後，開第二個網站不用再輸入密碼（單一登入）。

## 2. 動工前要決定

| 項目 | 外出單範例 |
|---|---|
| 網站名稱與資料夾 | `outing-portal` |
| 容器連接埠（NAS 內部） | `8001`（先確認沒人用，見步驟 B1） |
| 使用者連的 HTTPS 連接埠（DSM 反向代理） | `8444` |
| 資料庫與帳號 | 資料庫 `outing`，擁有者帳號 `outing_app` |
| authentik 應用名稱、client id | `Outing`、`outing` |
| 群組 | `Portal-Outing-Users`、`Portal-Outing-Admins` |
| 資料範圍 | 一般人只看自己的單，管理者看全部 |
| 要不要 n8n | 通知主管等需要時才要 |
| 誰維護這個功能的群組 | 至少 1～2 位同仁 |

連接埠現況（避開）：5678（n8n）、5433（Postgres）、5000／5001（DSM）、9000／9443（authentik）、8000／8443（EC Portal）。

## 3. 步驟總表

| 階段 | 做什麼 | 誰做 |
|---|---|---|
| A | 在開發電腦複製專案、改成新網站 | 開發者 |
| B | 在 NAS 準備：連接埠、資料庫 | 有 NAS 權限的人 |
| C | 在 authentik 新增應用與群組 | 有 authentik 管理權限的人 |
| D | 在 NAS 部署新網站容器 | 有 NAS 權限的人 |
| E | DSM 反向代理與憑證 | 有 DSM 權限的人 |
| F | 驗證權限與資料範圍 | 開發者 + 測試帳號 |

## 4. 階段 A：複製專案、改成新網站

1. 複製整個 `ec-portal` 資料夾成新資料夾（例如 `outing-portal`），**移除 `.git`**，建立新的 git repo 與新的 GitHub repo。
2. 新專案寫自己的 `CLAUDE.md`（專案簡報與決策表），不要沿用 EC 的決策內容；EC 的決策只留作參考。
3. **刪掉 EC 專用的部分**（刪前先確認新功能用不到）：

| EC 專用內容 | 位置 |
|---|---|
| EC 查詢功能 | `app/features/ec_query/` 全部、對應的範本（`ec_*.html`、`job_detail.html`、`jobs_list.html`、`_job_status.html`、`templates_list.html`、`admin.html` 等） |
| EC 的資料表與遷移 | `app/models.py` 的 EC 模型、`migrations/versions/0001_initial.py`（重新產生屬於新功能的初始遷移） |
| EC 的設定 | `app/config.py` 的 `n8n_ec_*`、`portal_callback_secret`、設備同步、查詢上限等；`DEFAULT_FEATURE_GROUPS` |
| 設備同步等排程 | `app/jobs/` 內 EC 的部分 |
| EC 的測試 | `tests/` 內 EC 相關 |

4. **留下來的共用骨架**（先複製，第 8 節會列出）：登入（`app/auth/`）、CSRF、`app/db.py`、`app/web.py`、`base.html`、`403.html`、`home.html`、`healthz`。
5. 本機驗證：`pytest` 與 `ruff check .` 通過，開發用假登入能進首頁。

### 一定要改的地方（沒改會出事）

| 項目 | 為什麼 | 改什麼 |
|---|---|---|
| **session cookie 名稱** | 兩個網站都在 `10.11.1.40`，只是連接埠不同；**瀏覽器的 cookie 不分連接埠**。兩邊都用預設名稱 `session` 的話，會互相覆蓋對方的登入狀態，使用者在兩個網站間切換會一直被登出、OIDC 登入流程也會失敗（未實測，依 cookie 規則推論） | `app/main.py` 的 `SessionMiddleware(...)` 加 `session_cookie="outing_session"`（名稱不能與 EC 的 `session` 相同） |
| **docker compose 專案名稱** | `deploy/portal/docker-compose.nas.yml` 開頭的 `name: ec-portal-web`。若新網站沿用同名，`up -d` 會被當成同一個專案，**可能把 EC Portal 的容器換掉** | 改成 `outing-web`；映像名稱 `ec-portal:nas` 也改成 `outing-portal:nas` |
| **連接埠** | 8000 已被 EC 使用 | `.env` 的 `PORTAL_HTTP_PORT=8001` |
| **OIDC 設定** | 要對應新的 authentik 應用 | `.env` 的 `OIDC_ISSUER`、`OIDC_CLIENT_ID`、`OIDC_CLIENT_SECRET`（見階段 C） |
| **群組對應** | 新功能用自己的群組 | `DEFAULT_FEATURE_GROUPS` 改成 `outing` 的群組 |
| **所有密鑰** | 不能與 EC 共用 | 新的 `SESSION_SECRET`、OIDC secret、n8n 密鑰 |
| **打包腳本** | 壓縮檔名稱與內容 | `make-nas-bundle.ps1` 的預設輸出檔名改成新名稱，並確認它有帶到新網站的所有檔案 |

## 5. 階段 B：NAS 準備

**B1 確認連接埠沒人用**（NAS 終端機）：

```bash
sudo netstat -tln | grep -E ':8001 |:8444 '
```

預期：沒有任何輸出。有輸出就換連接埠。

**B2 建立資料庫與帳號**：在 NAS Postgres（連接埠 5433）建立資料庫 `outing` 與擁有者帳號 `outing_app`。密碼自己產生並保管，**不要貼進聊天、不要進 repo**。連線字串寫進新網站 `.env` 的 `DATABASE_URL`（密碼含特殊字元要做百分比編碼；連線要 `?sslmode=disable`）。
若新功能要讀 `5070_db`（點位對照、通訊錄），另建唯讀帳號，只給需要的資料表 SELECT。

## 6. 階段 C：authentik 新增應用與群組

做法是**新增一個 blueprint 檔案**（例如 `outing.yaml`），放進 NAS 的 `/volume1/docker/ec-portal-authentik/blueprints/`，參考現有的 `ec-portal.yaml`。authentik 的 compose 已掛載整個 `blueprints` 資料夾，新檔案會被讀到。

### C1 新 blueprint 要有的內容

| 內容 | 重點 |
|---|---|
| 群組 | `Portal-Outing-Users`、`Portal-Outing-Admins`。照 `ec-portal.yaml` 的寫法，並授予權限管理者角色「檢視、加入成員、移除成員」，管理者才看得到、管得到 |
| OIDC provider | 名稱 `outing`；`client_id` 與 `client_secret` 用新的環境變數（例如 `OUTING_OIDC_CLIENT_ID`、`OUTING_OIDC_CLIENT_SECRET`）；`redirect_uris` 用新網站網址（登入回呼與登出各一筆） |
| 應用 | slug `outing`、名稱 `Outing`，綁定上述 provider |
| **進入條件（重要）** | 用**專屬於這個功能的規則**：`return any(g.name.startswith("Portal-Outing-") for g in request.user.groups.all())`。不要照抄 EC 的 `startswith("Portal-")`，否則所有 `Portal-*` 的人都能登入新網站 |

權限管理者角色有兩種做法：

- **沿用現有的 `PortalAdmin-GroupManagers`**：同一批人管所有功能的群組。blueprint 內用 `!Find` 引用既有角色，不要重新宣告（未實測）。
- **每個功能自己一個角色與管理者群組**：不同功能由不同的人管。管理者群組名稱**不要以 `Portal-` 開頭**。

### C2 新增環境變數並套用

1. 在 authentik 的 `.env` 加新的幾個變數（client id、secret、兩個 redirect URI）。secret 在 NAS 上產生：`openssl rand -hex 32`。
2. 重建讓環境變數生效：

```bash
cd /volume1/docker/ec-portal-authentik
sudo docker compose -f docker-compose.nas.yml up -d --force-recreate server worker
sudo docker compose -f docker-compose.nas.yml ps
```

3. 到 authentik 後台 → 自訂 → Blueprints，確認 `outing` 狀態為 Successful；沒有自動套用就手動套用。
4. 確認：目錄 → 群組有新群組；應用程式 → 應用程式有 `Outing`；提供者的 Redirect URIs 正確。

### C3 檢查現有 EC 應用的進入條件（建議一起處理）

EC 的進入條件目前是「屬於任一 `Portal-*` 群組」。新增 `Portal-Outing-*` 之後，**外出單的人也能通過 EC Portal 的 authentik 這一關**（進去後 EC 首頁顯示「目前沒有開放給你的功能」，直接開 `/ec/` 回 403，資料不會外洩，但不乾淨）。

建議把 EC 的規則改成只放行 `Portal-ECQuery-`。這會動到現有 EC 應用，**請先與負責人確認**，改完用沒有 EC 群組的測試帳號確認被擋、有 EC 群組的帳號仍可登入。

## 7. 階段 D～F：部署與驗證

### D 部署新網站（NAS，由人操作）

流程與 EC Portal 相同，照 `deploy/portal-deploy.md` 的第 1～5 節，把名稱、資料夾、連接埠換成新的：

1. 開發電腦打包新網站。
2. 在 NAS 建資料夾 `/volume1/docker/outing-web/`，上傳解壓。
3. 建 `.env`（`chmod 600`），填入：新的 `SESSION_SECRET`、`PORTAL_HTTP_PORT=8001`、`PUBLIC_BASE_URL=https://10.11.1.40:8444`、新的 `DATABASE_URL`、`OIDC_ISSUER=http://10.11.1.40:9000/application/o/outing/`（結尾要有斜線）、`OIDC_CLIENT_ID`、`OIDC_CLIENT_SECRET`（與 authentik 那邊的相同）。
4. `build` → `run --rm portal alembic upgrade head` → `up -d`，用 `ps` 確認 healthy，`curl http://127.0.0.1:8001/healthz` 回 `{"status":"ok"}`。

**部署前再確認一次：compose 專案名稱與映像名稱已改**，否則會影響到 EC Portal 的容器。

### E DSM 反向代理

1. 控制台 → 登入入口 → 進階 → 反向代理伺服器 → 新增：來源 HTTPS、主機 `10.11.1.40`、連接埠 `8444`；目的地 HTTP、`localhost`、`8001`。
2. 憑證沿用 EC Portal 那張（`10.11.1.40`），指定給新規則。
3. 若 DSM 防火牆有開：放行 8444（使用者來源）；要接 n8n 回呼的話也放行 8001。
4. 驗證：瀏覽器開 `https://10.11.1.40:8444/healthz`，接受憑證警告後顯示 `{"status":"ok"}`。

### F 驗證（至少這些案例）

| 案例 | 預期 |
|---|---|
| 有 `Portal-Outing-Users` 的人登入新網站 | 看得到並能用功能 |
| 只有 EC 群組的人登入新網站 | 在 authentik 被擋（Permission denied） |
| 沒有任何 `Portal-*` 群組的人 | 在 authentik 被擋 |
| 有 Users、開 admin 才能用的網址 | 403 |
| 使用者 A 開使用者 B 的資料 | 404，看不到內容 |
| 有 Admins | 看得到全部 |
| 表單 POST 沒帶 CSRF | 被拒絕 |
| **同一個瀏覽器先開 EC Portal、再開新網站，來回切換** | **都不需要重新登入、不會被登出**（驗證 cookie 名稱已分開） |
| EC Portal 在新網站部署後仍正常 | 首頁、查詢都正常（驗證沒影響到現有容器） |
| 登出後再開新網站 | 要求重新登入 |

## 8. 共用程式碼：先複製，記下來

第一版為了不互相影響，**直接複製**共用骨架。這是已知的取捨：修一邊的 bug 要記得修另一邊，兩邊會慢慢不同步。

請在新網站的 repo 維護一份清單，**記錄複製自哪個版本、之後有沒有各自改過**，作為第二個網站上線後討論共用的素材。目前看起來可能共用的部分（只是候選，不是決定）：

| 候選 | 位置 |
|---|---|
| OIDC 登入與登出 | `app/auth/oidc.py`、`app/auth/routes.py` |
| 授權（群組與角色） | `app/auth/permissions.py`、`app/auth/deps.py` |
| CSRF | `app/auth/csrf.py` |
| 設定與啟動安全檢查 | `app/config.py`、`app/main.py` 的 `check_startup_safety` |
| 資料庫連線 | `app/db.py` |
| 版型與樣式 | `app/web.py`、`app/templates/base.html`、`app/static/` |
| 使用者本人 email 的確認與對應（D4） | `app/features/ec_query/email_store.py`、`app/core/email_identity.py`、`app/core/recipients.py`、`app/core/directory.py`（目前放在 EC 功能內，要共用得先抽出來） |
| 部署檔 | `deploy/portal/`（compose、打包腳本、`.env` 範本） |

討論共用時要一併決定：共用程式庫怎麼發布與升版、各網站如何跟著更新、要不要有一個統一的入口首頁。

## 9. 需要 n8n 時

沿用 EC 查詢的契約模式（全文見 `01-architecture.md` 第 5 節）：網站 `POST` 到 n8n webhook（標頭帶密鑰）→ n8n 立刻回 `202` → 流程跑完後 `POST` 回網站的回呼網址更新狀態（`running`／`succeeded`／`failed`）。

- **回呼與狀態表要自己做**：EC 的回呼端點與 `jobs` 表是 EC 專用的，新網站自己建自己的表與回呼端點，用密鑰驗證（比對用 `secrets.compare_digest`），只允許更新狀態欄位；終態重複回報要冪等，狀態只能往前走，太久沒終態由網站排程標成逾時。
- **自己的 webhook 路徑與密鑰**：不要沿用 EC 的 `ec-portal-query` 或其密鑰。
- 回呼位址用 HTTP（例如 `http://10.11.1.40:8001`），因為 n8n 的回呼節點不接受自簽憑證。
- 新 workflow **建立後先停用**，人確認後才啟用；改任何 workflow 前，先把原始 JSON 備份到 `n8n/backups/`；**不要修改現行 EC 的三個 workflow**，要共用就建立複本。
- webhook 用 n8n 內建 Header Auth credential，密鑰不放進 workflow JSON；密鑰錯誤回 403。
- 測試信只寄給人提供的測試信箱。
- n8n 的寫入操作（建立、修改、啟用）用 REST API；唯讀查詢可用 MCP。

## 10. 之後更新新網站

與 EC Portal 相同：重新打包 → 上傳解壓覆蓋（`.env` 不在壓縮檔裡）→ 在網站資料夾執行 `build`、`run --rm portal alembic upgrade head`、`up -d`。只改 `.env` 時：`up -d --force-recreate portal`。更新時**只有這個網站會短暫重啟**，EC Portal 不受影響。

## 11. 完成時要更新的文件

- 新網站 repo 的決策紀錄與工作計畫。
- 記下群組名稱與維護者、連接埠與網址、資料庫名稱（避免日後連接埠衝突）。
- 備份：新資料庫、新網站 `.env`、authentik 的 blueprint 與 `.env`，都要納入 NAS 備份。

## 12. 常見問題

| 狀況 | 原因與處理 |
|---|---|
| 在兩個網站之間切換會被登出、或登入一直失敗 | session cookie 名稱相同被覆蓋；確認兩邊的 `session_cookie` 名稱不同 |
| 部署新網站後 EC Portal 不見了或被重建 | compose 專案名稱（`name:`）或映像名稱沒改，與 EC 相同 |
| 登入後 authentik 顯示 redirect_uri 錯誤 | 新應用的 Redirect URI 與新網站的 `PUBLIC_BASE_URL` 不一致（含連接埠與路徑） |
| OIDC 驗證失敗（`iss` 不符） | `OIDC_ISSUER` 要用與 token 相同的入口 `http://10.11.1.40:9000/application/o/outing/`，結尾要有斜線，不要用 9443 |
| EC 群組的人進得了新網站 | 新應用的進入條件寫成 `startswith("Portal-")` 而不是 `Portal-Outing-` |
| 新網站一律 403 | `DEFAULT_FEATURE_GROUPS`（或 `FEATURE_GROUPS`）沒設或拼錯；或使用者是加入群組之前登入的，要登出再登入 |
| 權限管理者看不到新群組 | 群組沒有授予管理者角色「檢視、加減成員」權限 |
| 改了 `.env` 或 blueprint 沒生效 | authentik 要 `up -d --force-recreate server worker`，blueprint 只在內容變動時重套，必要時到後台手動套用 |
| 本機測得過、NAS 上少檔案 | 打包腳本沒帶到新檔案類型（特別是 `static` 底下的檔案；專案已知 `pyproject.toml` 的 package-data 沒列 `static/*.css`） |
