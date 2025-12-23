# **Lane Following Final Project（V5 Ultimate Tuned）**

本專題為樹莓派自走車循線系統，支援兩種環境：

- **學校（白色線道）**：basic / challenge（直線與 S 彎）  
- **家用（黃色線道）**：直線 \+ 彎道（L+S）

---

## **1\. 專案內容與文件**

- 交付清單：`CONTENTS.md`（老師快速查看用）  
- 方法 / 流程 / 成果說明：`REPORT.md`  
- 操作方式（如何執行 / 如何切換 School & Home / 如何錄影）：`INSTRUCTION.md`  
- 版本與調參紀錄（家用黃線 / 學校白線）：`CHANGELOG.md`

---

## **2\. 成果影片（Demo Videos）**

影片皆放在 `data/videos/`：

- `demo_school_white_basic_straight.mp4`  
- `demo_school_white_basic_scurve.mp4`  
- `demo_school_white_challenge_straight.mp4`  
- `demo_school_white_challenge_scurve.mp4`  
- `demo_home_yellow_l_s.mp4`

---

## **3\. 環境與程式入口**

- 整理與上傳：Windows（本機）  
- 實際執行：Raspberry Pi（自走車本體）  
- 主程式入口：`src/main.py`  
- 原檔保留：`src/play8_final_home_school_v5_Ultimate_Tuned.py`

---

## **4\. 執行方式（Raspberry Pi）**

以下指令請在 Raspberry Pi 的 Terminal 執行，並在專案根目錄下操作。

### **4.1 安裝套件**

pip3 install \-r requirements.txt

**4.2 執行主程式 python3 src/[main.py]

**5.備註（Notes）**

若需切換「學校白線 / 家用黃線」的參數與調校策略，請參考：

CHANGELOG.md

INSTRUCTION.md

