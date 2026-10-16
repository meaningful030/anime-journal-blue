# 動漫手札

[開啟公開網站](https://meaningful030.github.io/anime-journal-blue/)

水藍色的個人動漫手札。公開網站使用 HTML、CSS 與少量 JavaScript，部署到 **GitHub Pages**；Python Flask 與 SQLite 只在你的電腦上執行。沒有公眾註冊，也沒有瀏覽器圖片上傳。

這是獨立專案，目前收錄 171 部站主提供的作品。截至 2026-10-16，包含回憶書架 162 部及近期手札 9 部；各季分開記錄，分類會隨日期更新。沒有使用其他專案的資料、帳號、憑證或 Git 歷史。

## 在自己的電腦開啟

需要 Python 3.11 以上。Windows 可雙擊 `start.cmd`，第一次會在本專案建立 `.venv` 並安裝必要套件，接著開啟預覽。不要將 Python 管理程式部署到外部主機或改成對外監聽。

或在此資料夾開啟 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

- 公開頁面預覽：<http://127.0.0.1:8000/>
- 本機管理頁：<http://127.0.0.1:8000/login>
- 關閉啟動視窗或按 Ctrl+C 即停止本機服務，不影響已發布的 GitHub Pages。

首次編輯前，在另一個終端機自行設定唯一站主：

```powershell
.\.venv\Scripts\python.exe manage.py init-owner
```

密碼至少 14 字，輸入時不會顯示。程式只儲存 scrypt 雜湊，沒有預設密碼。忘記密碼可重新執行同一指令；需輸入 `RESET` 確認並會登出所有既有 session。這是你電腦上的站主，與 GitHub 帳號分開。

## 日常使用

1. 啟動本機程式並登入。
2. 新增作品，每一季分開填寫**該季的原始首播日期**，不是觀看日期。
3. 寫心得；未勾選公開的項目保持本機草稿。
4. 如有照片，先儲存作品，再用下方本機指令匯入。
5. 確認內容適合公開後，勾選公開並儲存，按「產生公開網站」。
6. 開啟預覽確認，再將新版本推送到新的 GitHub 儲存庫。推送會觸發 Pages 更新。

「儲存」不會自動更新匯出檔；「產生公開網站」不會自動上傳 GitHub。公開網站沒有登入、編輯或圖片上傳按鈕，站主也必須回到自己的電腦整理內容。

## 分類規則

以 **Asia/Taipei 當天往前六個日曆月** 計算，含邊界日；目標月份沒有對應日期時取該月最後一天。

- 邊界日至今天：近期手札，顯示標題、心得與已匯入的照片。
- 邊界日以前：回憶書架，只顯示作品名稱與首播年月，例如 `2023／1`。
- 首播未知、未來日期、未公開草稿：不會匯出。

首播欄位可填 `YYYY-MM-DD` 或僅知月份時的 `YYYY-MM`，公開頁面統一顯示年月。不會為月份資料補上虛構的日期；整個月份均屬同一分類時才匯出，跨越半年邊界或本月尚未結束時暫不匯出。初始清單未註明季別的系列採首部電視動畫；《HUNTER×HUNTER》和《奇諾之旅》依站主指定採 2011、2017 新版，OVA／網路動畫採首次發行年月。

例如 2026-10-15 的邊界是 2026-04-15；2026-08-31 的邊界是 2026-02-28。瀏覽器每分鐘與重新切回頁面時更新顯示分類，使用台北時區而不是訪客所在地時區。這仍依賴訪客裝置時鐘正確。

GitHub Actions 另於台北時間每天約 00:17 重新發布，移除新部署檔案中已過半年的心得與圖片。排程可能延遲，公開儲存庫長期無活動時排程也可能被 GitHub 停用；這不影響頁面上的日期分類。未來日期作品須在首播後重新於本機匯出，才會首次公開。

## 本機匯入照片

管理頁會顯示每部作品的編號。以編號 1 為例：

```powershell
.\.venv\Scripts\python.exe manage.py import-image 1 "C:\自己的圖片\photo.jpg" --alt "這張照片的公開說明" --public-image
```

每部作品一張照片，再次匯入會取代目前的照片關聯。支援 JPEG、PNG、WebP，原檔最多 12 MiB、2,400 萬像素；匯入後長邊最多 1800 像素，重新編碼為 JPEG 並移除 EXIF、GPS 與其他中繼資料。原始檔案不會複製進專案。圖片不能透過瀏覽器上傳。

可在匯入指令加上 `--source-url "https://example.org/"`，在圖片下方顯示來源連結。近期手札均有「我的心得」區塊，尚未提供文字時顯示「待補」；公開頁面是閱讀頁，心得透過本機管理頁或在對話中提供後更新。本站兩張動畫主視覺分別來自 [FX 戰士久留美官方網站](https://fxkurumi-info.com/)與[尼古喵喵官方網站](https://yanineko-anime.com/)，權利歸原權利人所有。

**移除中繼資料不會遮蔽照片畫面中的人臉、地址、帳號或文字。** 照片、替代文字、作品名稱與心得都需要自己確認是否能公開。

## 私人資料與公開資訊的邊界

| 位置 | 內容 | 可否傳到公開 GitHub |
| --- | --- | --- |
| `instance/` | SQLite、密碼雜湊、session、草稿、圖片暫存、私人備份 | 不可；已列入 `.gitignore` |
| `site/` | 明確匯出的公開文字、已處理照片、網頁檔 | 可以，這就是公開網站 |
| `journal/`、`manage.py` 等 | 網站與管理工具原始程式，沒有管理憑證 | 可以 |

公開匯出與部署目錄為 `site/`，Windows 下會繼承專案的正常存取權限。舊 `public/` 若存在，僅保留於本機，不再匯出或發布。

較早作品的心得與照片不會包含在新匯出的資料中。不過，**曾經公開的文字與照片可能已存在 Git 歷史、瀏覽器快取、搜尋引擎或他人的下載副本中**。刪除、取消公開或移入文字書架，不能保證撤回先前公開的內容。不要把任何必須保密的資料勾選為公開。

網站沒有外部字型、追蹤程式、第三方圖片或前端管理金鑰。GitHub 本身仍可能記錄訪客 IP，詳見其隱私政策。

## 發布到全新的 GitHub Pages

本專案使用新儲存庫 [meaningful030/anime-journal-blue](https://github.com/meaningful030/anime-journal-blue)，不要連到舊儲存庫。GitHub Free 的免費 Pages 一般搭配公開儲存庫，程式與 `site/` 內容也因此公開。方案可能改變，不保證永久免費。

先完成本機匯出：

```powershell
.\.venv\Scripts\python.exe manage.py export
```

如果這個資料夾尚未有獨立 Git 儲存庫：

```powershell
git init -b main
git add .gitignore README.md requirements.txt run.py start.cmd manage.py refresh_public.py journal tests site .github
git status --short
```

確認待提交清單**沒有** `instance/`、`.venv/`、任何資料庫、金鑰或備份，再提交並連到自己新建的空白儲存庫：

```powershell
git commit -m "Create blue anime journal"
git remote add origin https://github.com/meaningful030/anime-journal-blue.git
git push -u origin main
```

若已設定遠端，不要重複執行 `git remote add`，先確認遠端指向這個新專案。日後更新只需重新匯出，再執行 `git add site`、`git commit -m "Update journal"` 和 `git push`。

在新儲存庫的 **Settings → Pages → Build and deployment → Source** 選擇 **GitHub Actions**，再到 **Actions → Publish public journal → Run workflow** 首次發布。之後更新檔案並推送至 `main` 會自動重新發布。等 Actions 成功後，以 GitHub 顯示的 Pages 網址為準。

工作流程只部署 `site/`，不會執行 Flask，也不會接觸本機 SQLite。不需要信用卡、Python 雲端主機或另外的資料庫服務；GitHub 的免費額度與條款仍適用。

官方說明（2026-10-15 查核）：[GitHub Pages 的靜態網站與免費方案](https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages)、[自訂 Pages 工作流程](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)、[Actions 排程限制](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。

## 備份與復原

```powershell
.\.venv\Scripts\python.exe manage.py backup
```

備份放在 `instance/backups/`，含作品、密碼雜湊與圖片，但不含有效登入 session。請自行保存在另一個私人位置，不能上傳公開儲存庫。GitHub 上的公開網頁不是完整資料備份。

需要復原時，先停止本機服務，另行保留現有 `instance/`，再把備份中的 `journal.sqlite3` 與 `photos/` 放回 `instance/`。程式會使用現有 session 金鑰，或在缺少時產生新金鑰；重新登入即可。備份也包含草稿與站主密碼雜湊，請妥善保管。

## 驗證

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
node tests/dates.test.cjs
```

Node.js 只用於可選的前端日期測試，不是執行網站的必要條件。測試內容是獨立暫存的合成資料，不會混入你的手札。

安全設計包含：Werkzeug scrypt、Flask 簽章 cookie 加伺服器 session 驗證、8 小時 session 效期、登出撤銷、Flask-WTF CSRF、登入限速、參數化 SQLite、Jinja 自動跳脫、前端 `textContent`、CSP、本機 IP 與 Host 限制，以及明確列出可匯出欄位。持有本機檔案存取權的人仍可修改資料或重設站主，請使用自己的作業系統帳戶保護電腦。
