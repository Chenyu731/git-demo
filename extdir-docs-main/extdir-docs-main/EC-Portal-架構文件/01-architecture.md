# EC Portal — 架構設計

## 1. 整體架構

```
瀏覽器（內網）
   │ HTTPS
   ▼
ec-portal（FastAPI 容器） ◄──── OIDC ────► authentik ──LDAP 389──► AD
   │  1. 建立 job（DB）
   │  2. POST 標準 JSON（帶密鑰）
   ▼
n8n（NAS）新 workflow「[Portal] EC Query」 ── 不經 LLM
   ├─ 展開設備 → TagName 清單
   ├─ 呼叫子流程：確認 TagName 批次登記（9VtYjz2wafctAhkE）
   ├─ 呼叫子流程：PI Data Export（VC6EnZ3n80WLx2ZX）→ 寄 Excel
   └─ 3. 回呼 ec-portal（帶密鑰）更新 job 狀態
```

全部服務在 NAS 的 Docker；網站、authentik 各自一個 Container Manager 專案。

## 2. 元件與責任

| 元件 | 責任 | 不負責 |
|---|---|---|
| ec-portal | 登入流程（OIDC client）、群組授權、表單驗證、時區換算、job 管理、紀錄、範本、設備快取 | 碰密碼、直接打 PI |
| authentik | 帳密驗證、AD 群組同步、發 OIDC token | 業務邏輯 |
| n8n workflow | 固定流程執行 PI 查詢與寄信、回報結果 | 判斷使用者權限（但要驗密鑰） |
| NAS Postgres | `ec_portal` 資料庫（網站）、`5070_db`（點位對照，唯讀）、`email_mapping`（通訊錄，唯讀） | — |

## 3. 權限模型

依決策 D8、D9：AD 只驗證身分；功能權限來自 **authentik 自建群組**（不在 AD），由本單位維護。

### 3.1 通用規則

- 整個網站在 authentik 只註冊**一個應用**，使用者登入一次，網站從 OIDC 取得此人的所有群組。
- authentik 應用的進入條件：屬於任一 `Portal-*` 群組即可登入。進入後，每個功能再各自檢查。
- 每個功能在設定檔（`FEATURE_GROUPS`）宣告自己的角色與允許的群組；程式碼只引用「功能代號 + 角色」，**不寫死群組名稱**。
- **每個路由都要有授權檢查**，用 FastAPI dependency `require_feature(feature_id, role)` 統一實作。首頁只列出使用者有權限的功能。
- 沒有任何 `Portal-*` 群組的人：不會通過 authentik 的進入條件。有群組但沒有該功能的權限：HTTP 403。
- 不同功能開給不同對象，靠不同群組達成；同一個人可同時屬於多個群組。

### 3.2 群組清單（命名規則 `Portal-<功能>-<角色>`）

| 群組 | 權限 |
|---|---|
| `Portal-ECQuery-Users` | 使用 EC 查詢、看自己的紀錄、管理自己的範本 |
| `Portal-ECQuery-Admins` | 上述全部 + 看所有人紀錄 + 手動觸發設備同步 |
| `Portal-Outing-*` | 外出單（之後的功能，只列出示範，第一版不實作） |

### 3.3 群組維護

- 群組建立與成員增減：由本單位指定的同仁，在 authentik 管理後台操作；用 authentik 的「角色」把「看群組、加人、移除人、進入管理後台」權限委派給他，**可限縮到特定群組**，並另需「看使用者」權限。
- AD 使用者先同步進 authentik，才能被加入群組。
- 網站本身不提供加人或權限管理介面。

### 3.4 資料範圍

授權只決定「能不能進功能」；功能內的資料範圍由功能自己定義並測試。EC 查詢：一般使用者只看自己的 jobs，Admins 看全部。

## 4. 資料模型

### `jobs`

| 欄位 | 型別 | 說明 |
|---|---|---|
| id | UUID PK | 同時作為 n8n 的 job_id |
| user_sub | text | OIDC subject |
| user_email | text | |
| mode | enum `equipment` / `tags` | |
| equipment | text null | mode=equipment 時 |
| tags | text[] | mode=tags 時為使用者輸入；mode=equipment 時記錄展開結果 |
| start_utc / end_utc | timestamptz | |
| interval | enum | 見第 6 節 |
| recipients | text[] | |
| status | enum `queued` / `running` / `succeeded` / `failed` | |
| error_code / error_message | text null | |
| missing_tags | text[] null | 確認登記時找不到的 TagName |
| n8n_execution_id | text null | |
| created_at / updated_at / finished_at | timestamptz | |

### `templates`

id、user_sub、name、params（JSONB，同查詢表單欄位，時間存「相對」或「固定」兩種）、created_at。

### `equipment_cache`

equipment（PK）、tag_names（text[]）、descriptions（JSONB）、synced_at。由排程從 `PIHistorianMappingTable` 同步。

### `user_email_map`（使用者與 email 的對應，D4）

| 欄位 | 說明 |
|---|---|
| sam_account_name | PK，AD 的 sAMAccountName（小寫存放） |
| employee_no | 帳號為 `U0` + 數字時推得，否則 null（僅供參考，不當對應鍵） |
| email | 此人的收件地址，必須是 `@ecic.com.tw` 且存在於 `email_mapping` |
| source | `preselected_confirmed`（使用者接受預選的 N）/ `suggested`（使用者接受預選的 L）/ `user`（使用者從下拉自選）/ `admin`（管理者指定或種子名單） |
| confirmed_at | 使用者或管理者確認的時間，**一律有值（不可為 null）**；沒有確認就不寫入這張表 |

### `user_email_audit`（對應表變更稽核）

id、sam_account_name、old_email（null 表示首次確認）、new_email、source、changed_by（使用者本人或管理者帳號）、changed_at、reason（管理者修改時必填）。每次寫入或修改 `user_email_map` 都要同時寫一筆。

## 5. n8n 契約（各工作線共同介面，修改需人同意）

### 5.1 網站 → n8n：送出查詢

`POST {N8N_EC_WEBHOOK_URL}`
Header：`X-EC-Secret: {N8N_EC_SECRET}`、`Content-Type: application/json`

```json
{
  "job_id": "0b6c9f0e-1c1a-4c1e-9a43-2f2b8d0d2a11",
  "mode": "equipment",
  "equipment": "V3-1",
  "tags": [],
  "start": "2026-11-01T02:00:00Z",
  "end": "2026-11-02T02:00:00Z",
  "interval": "1h",
  "recipients": ["a@ecic.com.tw"],
  "requested_by": "a@ecic.com.tw",
  "callback_url": "https://ec-portal.內網/api/internal/jobs/0b6c9f0e-.../status"
}
```

規則：
- `start` / `end` 一律 UTC、ISO 8601、`Z` 結尾。
- `mode=equipment` 時 `tags` 為空，由 n8n 展開；`mode=tags` 時 `equipment` 為 null。
- `interval` 網站送 `1d`，n8n 轉成 `24h` 再傳給匯出流程（現行子流程只解析 s／m／h，見 D13）。
- `recipients` 可多人：n8n 使用匯出子流程的複本（固定寄件者、支援多收件人），不修改原子流程（D13）。
- TagName 登記檢查由新流程直接查 Postgres `tagname_webid_table`（D6），任何一個未登記就回呼 `failed/TAGS_NOT_REGISTERED`，不進入匯出。
- n8n 收到後**立即**回 `202 {"accepted": true, "execution_id": "..."}`，不等查詢完成。
- 密鑰錯誤回 `403`（n8n 內建 Header Auth 的行為，D14；原訂 401），欄位錯誤回 `400 {"error_code": "INVALID_REQUEST", "message": "..."}`。

### 5.2 n8n → 網站：回報狀態

`POST {callback_url}`
Header：`X-EC-Secret: {PORTAL_CALLBACK_SECRET}`

```json
{
  "job_id": "0b6c9f0e-...",
  "status": "running | succeeded | failed",
  "error_code": null,
  "error_message": null,
  "missing_tags": [],
  "execution_id": "12345"
}
```

規則：
- 至少回報一次 `running` 與一次終態（`succeeded` 或 `failed`）。
- 狀態只能往前走（queued → running → 終態）；網站忽略倒退的回報並記 log。
- 網站對同一終態的重複回報要冪等。

### 5.3 錯誤代碼

| error_code | 意義 |
|---|---|
| `TAGS_NOT_REGISTERED` | 有 TagName 未登記於 WebID 表（`missing_tags` 列出） |
| `EQUIPMENT_NOT_FOUND` | 設備在對照表找不到 |
| `PI_API_ERROR` | PI Web API 呼叫失敗 |
| `EMAIL_FAILED` | 寄信失敗 |
| `TIMEOUT` | 網站端：超過 N 分鐘沒有終態（由網站排程標記） |
| `INVALID_REQUEST` | 只出現在 n8n 對送出請求的同步 400 回應（欄位錯誤）；不會出現在回呼 |
| `INTERNAL` | 其他 |

## 6. 查詢參數規則

| 參數 | 規則 |
|---|---|
| 時間輸入 | 台北時間，日期 + 時 + 分（下拉選分鐘，步進 5 分） |
| 時間換算 | 網站程式碼用 `zoneinfo("Asia/Taipei")` 轉 UTC；必須有單元測試覆蓋「台北 10:00 → 02:00Z」 |
| 範圍 | end > start；最長範圍上限放設定檔（暫定 31 天） |
| 間隔 | 下拉固定選項：`1m`、`5m`、`10m`、`30m`、`1h`、`1d`（實際可用值由 N0 盤點 PI Export 子流程確認） |
| 點數預估 | 送出前估算「tag 數 × 時間點數」，超過上限（暫定 100000，對應子流程的 SAFE_TOTAL_LIMIT）時提示使用者縮小範圍 |
| 收件人 | 依 D4：預設收件人為登入者本人的 email（解析規則見 6.1）；額外收件人最多 5 個，必須是 `@ecic.com.tw` 且存在於 `email_mapping`（網站以唯讀帳號查詢，可快取） |

### 6.1 登入者本人 email 的解析規則（D4）

AD 的 `mail` 欄位幾乎是空的，**不可作為來源**；`email_mapping` 沒有帳號或工號，**不可用工號比對**。診斷（2026-11-02，896 個啟用帳號）後的規則用兩個候選：

- **候選 N（名字比對）**：OIDC 帶來的 `displayName`（前後空白去除後）完全等於 `email_mapping.name`，**剛好一筆**、該筆 email 是 `@ecic.com.tw`，**且**這個 `displayName` 在 AD 只有一個帳號使用。三項都成立才有 N。
- **候選 L（帳號比對）**：`sAMAccountName`（不分大小寫）等於 `email_mapping` 中某筆 `@ecic.com.tw` 地址的 `@` 前段，且只有一筆。`U0` 帳號通常沒有 L。

解析順序：

**原則：沒有人會被靜默帶入。** 每位使用者都要在「確認你的 email」頁自己確認一次；候選 N、L 只決定頁面上**預選什麼**。

1. 先查 `user_email_map`（以 sAMAccountName，不分大小寫）。有紀錄就直接用，**不再詢問**。
2. 沒有紀錄時，進入任何需要本人 email 的功能前，一律導向「確認你的 email」頁。頁面的預選依候選決定：
   - **有 N，且（沒有 L 或 L 與 N 相同）** → 預選 N；使用者按確認後寫入（`source=preselected_confirmed`）。
   - **有 N 也有 L，但兩者不同**（約 1%）→ **不預選**，兩個都列出，另附搜尋下拉；使用者選定後寫入（`source=user`）。
   - **沒有 N，只有 L**（含 `displayName` 共用同名的 B 類、以及比對不到名字的人）→ 預選 L 作為建議；使用者按確認後寫入（`source=suggested`）。
   - **都沒有** → 不預選，使用者從通訊錄下拉搜尋選擇（只含 `@ecic.com.tw` 地址），選定後寫入（`source=user`）。
3. 使用者按確認之前**不寫入任何資料**；寫入時 `confirmed_at` 一律有值，並同時寫一筆 `user_email_audit`。
4. 事後更改已確認的 email **只有管理者**（`Portal-ECQuery-Admins`）能做，必須填原因，並留稽核紀錄；管理者也可匯入種子名單（`source=admin`）。

預期約 739／896（82%）會有預選項目；其餘約 157 位（17.5%）沒有預選、需手動選，他們多半不在 Domino 通訊錄（外包、約聘、資訊、系統帳號），AD 端再加規則補不回來。去除空白與標點的正規化救回 0 個，所以**不做**正規化；姓氏加名字、差一個字的比對第一版也**不採用**。

規則：
- 預選項目使用者都看得到並可改選，且只能從通訊錄選，不能自由輸入。
- 風險：使用者第一次選擇時可能選到別人的公司 email（冒用）。緩解：只能選通訊錄內的人；確認動作有紀錄（`confirmed_at`、`user_email_audit`）；事後更改只有管理者；稽核靠查詢紀錄（jobs 有收件人與登入者）。
- 必須有測試：N 與 L 一致時預選 N（未確認不寫入）；只有 N 時預選 N（未確認不寫入）；N 與 L 不一致時不預選且兩者都列出；只有 L 時預選 L（未確認不寫入）；同名（B 類）不預選 N；非 `@ecic.com.tw` 不採用；已有對應紀錄時不再詢問；**沒有任何情況會在使用者確認前寫入對應表**；寫入的紀錄 `confirmed_at` 都不是 null 且有稽核紀錄；非管理者不能改已確認的 email；`displayName` 缺漏時只能走 L 或手動；`U0` 帳號沒有 L 時走 N；比對前去除前後空白、大小寫只對 L 不分，其餘不做模糊比對。
- 開放問題（尚未測試）：一般員工帳號的 `proxyAddresses`、`otherMailbox` 是否帶有 email（服務帳號自己的物件測不出來）；公司 email 用於 Google Chat，可能有 Google Workspace 目錄可作為帳號與 email 的權威來源（未證實）；或請人資／IT 提供一次性名單補其餘帳號。

## 7. 安全

| 項目 | 做法 |
|---|---|
| 登入 | 只走 authentik OIDC（Authorization Code + PKCE）；網站不收密碼 |
| Session | 簽章 cookie、HttpOnly、Secure、SameSite=Lax、有效期 8 小時 |
| CSRF | 表單 POST 帶 CSRF token |
| 授權 | 每個路由的 dependency 檢查群組；資料查詢加 `user_sub` 過濾 |
| n8n webhook | Header 密鑰 + 只接受 NAS 內網來源 |
| 回呼端點 | Header 密鑰；只允許更新狀態欄位；不需登入但不能讀資料 |
| 開發用假登入 | 只在 `APP_ENV=dev` 時存在，正式環境啟動時若偵測到要直接拒絕啟動 |
| 稽核 | jobs 表本身即查詢紀錄；登入紀錄由 authentik 保存 |
| AD 連線加密 | D10：authentik 到 AD 走 LDAP 389 明文（內網，已核准）；密碼在 authentik 與 DC 之間以明文傳送，屬已接受的風險。使用者瀏覽器到 authentik／網站走 HTTPS（DSM 自簽憑證，D12） |

## 8. 專案結構

```
ec-portal/
├── CLAUDE.md                 # 由 00-project-brief.md 而來
├── docs/                     # 本規劃文件 + n8n 盤點結果
├── app/
│   ├── main.py
│   ├── config.py
│   ├── db.py
│   ├── auth/                 # OIDC、dev 假登入、授權 dependency
│   ├── core/                 # 時間換算、共用驗證
│   ├── features/
│   │   ├── registry.py       # 功能登記（名稱、說明、關鍵字、路徑、所需群組）
│   │   └── ec_query/         # routes、service、schemas、n8n_client、templates
│   ├── jobs/                 # 排程：設備同步、逾時標記
│   └── templates/            # 共用版型
├── migrations/
├── tests/
├── deploy/
│   ├── portal/compose.yml
│   └── authentik/            # compose.override.yml、.env.example、blueprints/
├── n8n/
│   ├── backups/              # 現行 workflow 原始 JSON 備份
│   └── ec-query-fixed.json   # 新 workflow 的匯出版本（版控用）
├── Dockerfile
├── .env.example
└── pyproject.toml
```

## 9. 功能登記（為日後導覽 / AI 助手預留）

`app/features/registry.py` 每個功能必填：`id`、`name`、`description`、`keywords`、`path`、`required_groups`。
首頁依登入者群組列出可用功能。之後若做 AI 助手，只把「該使用者可用的登記項」交給模型，模型只能回傳 `id`，連結由程式組。
