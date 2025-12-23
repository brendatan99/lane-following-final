![GitHub Workflow Diagram](./GitHub_diagram.png)

## 1) 專案內文件版：`docs/GIT_WORKFLOW.md`

> 你在專案根目錄新增資料夾 `docs/`，再新增檔案 `docs/GIT_WORKFLOW.md`，把以下整段貼進去即可。

````md
# GitHub 上傳流程筆記（Windows + PowerShell）

本文件整理「從本機專案準備 → Git 初始化 → Commit → Push → 後續更新」完整流程。
適用於包含 `src/`、`data/`、多個 `.md` 與影片/圖片的專題專案。

---

## 0. 前置：進到專案根目錄

在 PowerShell 進入你的專案根目錄（所有指令都在這裡做）：

```powershell
cd C:\Users\88691\projects\lane-following-final
````

預期：提示字元變成 `PS ...\lane-following-final>`。

---

## 1. 建立/確認專案骨架（資料夾與檔案）

### 1.1 檢查根目錄有哪些檔案與資料夾

```powershell
Get-ChildItem
```

### 1.2 若缺資料夾就建立（需要才做）

```powershell
New-Item -ItemType Directory -Force src
New-Item -ItemType Directory -Force data
New-Item -ItemType Directory -Force data\videos
New-Item -ItemType Directory -Force data\images
New-Item -ItemType Directory -Force docs
```

### 1.3 建立空的文件檔（需要才做）

```powershell
New-Item -ItemType File -Force README.md
New-Item -ItemType File -Force CONTENTS.md
New-Item -ItemType File -Force INSTRUCTION.md
New-Item -ItemType File -Force REPORT.md
New-Item -ItemType File -Force CHANGELOG.md
New-Item -ItemType File -Force requirements.txt
New-Item -ItemType File -Force .gitignore
```

---

## 2. MD 中文亂碼處理（重要）

### 方法 A：Google Docs 轉碼（穩定）

1. 把要寫入 `.md` 的內容貼到 Google Docs（Markdown 語法照貼）
2. 下載成 Markdown (.md)
3. 放回專案路徑覆蓋原檔
4. 用 Notepad++ 打開確認中文正常

### 方法 B：Notepad++ 直接貼入（更快）

1. 用 Notepad++ 打開空的 `.md`
2. 貼入完整內容
3. Encoding 設為 UTF-8（Convert to UTF-8 或 UTF-8 without BOM）
4. 存檔，關掉再開一次確認

### 常見問題：整段變綠（被當程式碼區塊）

原因：出現未關閉的 code fence（少了結尾 `），或多貼了 `md。
修法：刪掉多餘的 `md 或補上結尾 `。

---

## 3. 檢查檔案是否在正確路徑、是否為空

### 3.1 列出資料夾內容

```powershell
Get-ChildItem .\src
Get-ChildItem .\data\videos
Get-ChildItem .\data\images
Get-ChildItem .\docs
```

### 3.2 查看文件內容（避免 0KB 骨架）

```powershell
Get-Content .\README.md
Get-Content .\CONTENTS.md
Get-Content .\INSTRUCTION.md
Get-Content .\REPORT.md
Get-Content .\CHANGELOG.md
Get-Content .\requirements.txt
```

---

## 4. 掃描是否還有 TODO 沒補（驗收用）

```powershell
Select-String -Path *.md -Pattern "TODO" -SimpleMatch
```

預期：

* **有輸出**：代表還有 TODO 行需要補
* **沒輸出**：代表 md 內容大致完整

---

## 5. requirements.txt 整理（從 import 輔助檢查）

### 5.1 列出 main.py 的 import 行

```powershell
Select-String -Path .\src\main.py -Pattern "^\s*(import|from)\s+" | Select-Object -ExpandProperty Line
```

用途：輔助你確認需要哪些套件。

### 5.2 建議寫入 requirements.txt 的格式（範例）

```
numpy
flask
opencv-python
picamera2
libcamera
```

---

## 6. .gitignore（建議內容）

```gitignore
# Python cache
__pycache__/
*.pyc
*.pyo
*.pyd

# Virtual environments
.venv/
venv/
env/

# OS junk
.DS_Store
Thumbs.db
Desktop.ini

# Editors
.vscode/
.idea/

# Logs & temp
*.log
temp/
output/

# Optional local configs
*.local.json
```

檢查：

```powershell
Get-Content .\.gitignore
```

---

## 7. GitHub 網頁端建立新 Repo（一次性）

在 GitHub 建 repo：

* Public（依課程規定）
* 不要勾 README / .gitignore / license（因為本機已準備）

建立完成後，會拿到 repo URL，例如：

* Repo：`https://github.com/<user>/<repo>`
* Git：`https://github.com/<user>/<repo>.git`

---

## 8. Git 初始化 → Add → Commit → Push（第一次上傳）

### 8.1 初始化

```powershell
git init
```

### 8.2 設定作者資訊（只要做一次）

> 建議用「GitHub 帳號已驗證的 email」。名字可用真名或 GitHub 顯示名（保持一致即可）。

```powershell
git config --global user.name "你的名字或顯示名"
git config --global user.email "你的GitHub已驗證Email"
```

檢查：

```powershell
git config --global --list
```

### 8.3 加入全部檔案追蹤

```powershell
git add .
```

### 8.4 檢查狀態

```powershell
git status
```

### 8.5 Commit

```powershell
git commit -m "Final project: lane following v5 (white/yellow) + docs + demos"
```

### 8.6 分支改名 main（對齊 GitHub）

```powershell
git branch -M main
```

### 8.7 綁定遠端

```powershell
git remote add origin https://github.com/<user>/<repo>.git
git remote -v
```

### 8.8 Push

```powershell
git push -u origin main
```

預期：若要求登入，依提示完成瀏覽器授權；成功後會看到 objects 上傳完成。

---

## 9. 後續更新（例如補 repo URL / 改文件）固定四步

### 9.1 看狀態

```powershell
git status
```

### 9.2 add（可用單檔或全部）

```powershell
git add CONTENTS.md
# 或：git add .
```

### 9.3 commit

```powershell
git commit -m "Update CONTENTS.md"
```

### 9.4 push

```powershell
git push
```

---

## 10. 最終驗收

```powershell
git status
```

預期：

```
nothing to commit, working tree clean
```

表示本機乾淨且已同步至 GitHub。

---

````

---

