# Kindle 天氣＋滙率看板

給 Kindle Paperwhite（E-ink）瀏覽器睇嘅超簡單網頁，每小時自動更新：

1. Leeds 即時天氣／溫度（UK Met Office）
2. Leeds 今日逐小時天氣／溫度（UK Met Office）
3. Leeds 未來 5 日天氣／溫度（UK Met Office）
4. 港元對英鎊／日圓／歐元滙率（Frankfurter／歐洲央行參考價）

## 運作方式

GitHub Actions 每小時跑一次 `generate.py`，抓最新數據，重新產生 `index.html`
並 commit；GitHub Pages 負責 hosting。Kindle 版面本身每小時自動重新整理
（`<meta http-equiv="refresh" content="3600">`），唔需要 JavaScript。

## 設置步驟

1. 去 https://datahub.metoffice.gov.uk/ 註冊（免費），訂閱
   **Site Specific – Global Spot**（免費計劃，每日 360 次），複製 API key。
2. 將呢個 repo 推上 GitHub（public repo）。
3. Repo → Settings → Secrets and variables → Actions → New repository secret，
   名叫 `METOFFICE_API_KEY`，貼上 API key。
4. Repo → Settings → Pages → Build and deployment → Deploy from a branch →
   Branch 揀 `main`、`/ (root)`，Save。
5. Actions → "Hourly dashboard update" → Run workflow，跑一次即刻有數據。
6. 喺 Kindle Experimental Browser 打開 `https://<用戶名>.github.io/<repo名>/`。

## 檔案

- `generate.py` — 抓數據＋產生 `index.html`（Kindle-safe 純 HTML，黑白大字）
- `.github/workflows/update.yml` — 每小時自動更新
- `index.html` — 產生出嚟嘅版面（唔好手改，會被覆蓋）
