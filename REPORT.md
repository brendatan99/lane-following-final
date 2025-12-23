# 期末專題報告（REPORT）

## 1. 專題目標
本專題目標為使用 Raspberry Pi 自走車完成循線任務，並能在不同環境下穩定運行：
- 學校白色線道：basic / challenge（含直線與 S 彎）
- 家用黃色線道：直線 + 彎道（L+S）

---

## 2. 系統架構
### 2.1 硬體
- Raspberry Pi 自走車平台
- 前置攝影機
- 馬達與驅動板（由程式呼叫控制模組控制）

### 2.2 軟體
- OpenCV：影像處理、遮罩、線道抽取
- Flask：網頁控制台（即時畫面、參數調整、錄影控制）
- 控制模組：`LOBOROBOT2.py`（負責馬達/車體控制）

---

## 3. 方法與流程（概述）
1. 影像擷取：相機取得即時影像。
2. ROI 取樣：擷取地面線道的有效區域，降低背景干擾。
3. 遮罩/二值化：
   - 白線模式：以亮度/門檻為主，抑制反光干擾。
   - 黃線模式：以顏色/HSV 或亮度差異抽取線道。
4. 中心偏差（CTE）計算：計算線道中心與畫面中心的差值。
5. 控制輸出：依偏差輸出轉向（並搭配速度策略）以達成循線。

---

## 4. 參數調校策略（Home / School）
- 學校白線：
  - 需處理反光與亮度波動，避免誤判線道。
  - basic 與 challenge 在彎道處需更快的轉向反應。
- 家用黃線：
  - 以顏色特徵抽取黃線，彎道段需提高前視與轉向反應。

> 詳細調參變更與版本紀錄請見 `CHANGELOG.md`。

---

## 5. 實驗結果（成果影片）
成果影片皆位於 `data/videos/`：
- `demo_school_white_basic_straight.mp4`
- `demo_school_white_basic_scurve.mp4`
- `demo_school_white_challenge_straight.mp4`
- `demo_school_white_challenge_scurve.mp4`
- `demo_home_yellow_l_s.mp4`

---

## 6. 結論
本專題完成不同環境（學校白線 / 家用黃線）之循線功能，並提供控制台進行即時觀察與參數調整，以提升測試效率與穩定性。
