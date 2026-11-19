# 範例畫面原始碼（plant1.html）

線上版：https://shinu0750.github.io/demo-Roger/plant1.html

| 檔案 | 作用 |
|---|---|
| `一廠分機表.xlsx` | 貼牆表的原始 Excel（建置資料的來源，也是驗證列印結果的標準答案） |
| `build_data.py` | 讀 Excel，整理成部門與人員資料，輸出 `data.json` |
| `data.json` | 範例裡所有的資料 |
| `template.html` | 頁面外觀（CSS）與骨架 |
| `app.js` | 全部功能邏輯：搜尋、異動收件匣、編輯、部門表、貼牆版排版、列印檢查 |
| `build.py` | 把上面三個組成單一檔案 `plant1.html` |
| `old-eip-plant1.html` | 舊 EIP 範例，`build_data.py` 只用它取共用人員資料 |

重新產生：`python build_data.py`（需要 openpyxl）再 `python build.py`。
