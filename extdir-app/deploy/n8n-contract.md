# n8n 與分機通訊錄的介面約定

n8n 只做兩件事：每天取 Domino 名冊丟給本系統、把本系統產生的彙整內容寄給廠務。判斷邏輯全在本系統，n8n 不做決定。
**這兩個 workflow 尚未建立**（需要 NAS 上的 n8n 與 Domino API，無法在開發環境測試）。依 EC Portal 05 指南第 9 節的原則：新 workflow 建立後先停用、人確認後才啟用；改任何 workflow 前先備份原始 JSON；不要修改現行 EC 的三個 workflow；密鑰用 n8n 內建 Header Auth credential，不放進 workflow JSON。

所有呼叫都帶標頭 `X-Internal-Secret: <INTERNAL_API_SECRET>`，錯誤回 403。網址用 NAS 內部 HTTP：`http://10.11.1.40:8002`。

## 1. 每日比對　`POST /api/internal/domino-sync`

```json
{
  "people": [
    {"email": "a@example.com", "name": "王小明", "dep": "一廠製三組", "title": "", "supervisor": "李大華"}
  ],
  "baseline": false,
  "bring_in_unlisted": false
}
```

- `people` 必須是 Domino 的**完整**名冊（空名冊會被拒絕）。email 為空的筆數會被略過。
- 回應：`{"run_id": "...", "abnormal": false, "auto": 3, "pending": 1, "leave": 0}`。
- `abnormal: true` 表示本次離職超過 5 人或 3%，整批改為待確認（防 Domino API 回傳不完整），請在彙整信中特別標示。
- **第一次**（建置）：`baseline: true` 只補 Email 與建立名冊，不產生異動；回應列出 `linked`、`ambiguous`（同名）、`not_found`。`bring_in_unlisted: true` 另外把貼牆表沒列名的人，依部門預設分機帶入（需求第 9 節第 6 項尚待廠務決定，先不要開）。

## 2. 彙整信內容　`GET /api/internal/domino-digest?run_id=<run_id>`

回傳 `{"auto": [...], "pending": [...]}`，每筆有 `kind`、`name`、`from`、`to`、`reason`。靜默項目（Email 為 f＋數字）已排除、不通知。
n8n 依此寄一封信給廠務，分「已自動處理」與「待你確認」兩段；待確認要附維護頁連結 `https://10.11.1.40:8445/admin/`。收件者名單由廠務維護人員名單決定（需求第 9 節第 2 項，尚未提供）。

## 與需求文件的差異

需求 3、7 寫「匯出時由系統呼叫 n8n 產 Excel（202＋callback）」。目前改為**本系統直接產生 Excel**（openpyxl，下載即得），不依賴 n8n，也沒有回呼與逾時處理的複雜度。若之後有理由要走 n8n（例如要自動寄信），再補。
