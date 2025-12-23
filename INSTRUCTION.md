---

# 操作方式（INSTRUCTION）

本文檔說明如何在 Raspberry Pi（自走車）上執行本專題程式，以及如何錄影與切換環境（學校白線 / 家用黃線）。

---

## 1. 執行方式（Raspberry Pi）

在專案根目錄下：

### 1.1 安裝套件
```bash
pip3 install -r requirements.txt
````

### 1.2 執行主程式

```bash
python3 src/main.py
```

---

## 2. 操作介面（Flask 控制台）

開啟網頁控制台後，可進行：

* 開始循線 / 立即停止
* 參數調整（PID、ROI、遮罩模式等）
* 錄影切換（Recorder ON/OFF）

控制台網址與埠號以程式啟動後 Terminal 顯示為準。

---

## 3. 環境切換（School / Home）

* 學校白線：以白線辨識為主（basic / challenge）
* 家用黃線：以黃線辨識為主（直線 + 彎道）

詳細參數調校與版本差異請見 `CHANGELOG.md`。

---

## 4. 錄影輸出

錄影輸出路徑與檔名規則依程式設定為準。建議測試流程：

1. 先確認即時畫面正常
2. 再開始錄影
3. 跑完再停止錄影，避免檔案不完整

````

---

