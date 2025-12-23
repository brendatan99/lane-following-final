# 版本與調參紀錄（CHANGELOG）

本文檔整理本專題在「學校白線」與「家用黃線」兩種環境下的最終調參結果與重點（以控制台最後一次設定為準）。

---

## V5 Ultimate Tuned（Final）— 2025-12

### A. 學校白線（School / White）— 最終設定（白線）
**目標：** 穩定通過學校白線 basic / challenge（直線 + S 彎），並降低反光造成的誤判。

#### A1. POWER & PID
- Speed：45
- Kp (Turn)：0.55
- Kd (Stable)：1.02
- CurveSlow：0.90

#### A2. S-CURVE & OPTION
- LookAhead：26
- LaneWidth：160
- Boost：1.20

#### A3. LANE LOGIC (V4)
- MaskMode：1
- MaxCov：0.65
- MaskPx：66
- YelPx：250
- ROI Min：76
- BandH：90
- PeakMin：6
- LaneWMin：40

#### A4. STEERING (V4)
- Gain：2.40
- Limit：70
- Timeout：0.70
- Coast：0.55

#### A5. WHITE HSV（白線模式）
- H 色相：0 / 180
- S 飽和：43 / 88
- V 明度：173 / 255

#### A6. YELLOW HSV（保留參數；白線時通常不主用）
- H 色相：15 / 45
- S 飽和：20 / 255
- V 明度：80 / 255

#### A7. 已知現象與對策（白線）
- 反光誤判：優先調整 WHITE HSV（V/門檻）與 ROI Min，使 ROI 聚焦地面線道區域。
- 彎道抖動：可微調 Kp↓ / Kd↑、或降低 Speed、或提高 CurveSlow（讓彎道降速更明顯）。
- 偏離中心：可微調 LaneWidth、LookAhead 與 Steering Gain（但避免過衝）。

---

### B. 家用黃線（Home / Yellow）— 最終設定（黃線）
**目標：** 家用黃線直線不飄、彎道能順利進彎出彎（L + S），並維持連續不中斷。

#### B1. POWER & PID
- Speed：50
- Kp (Turn)：0.55
- Kd (Stable)：0.41
- CurveSlow：0.65

#### B2. S-CURVE & OPTION
- LookAhead：5
- LaneWidth：160
- Boost：1.00

#### B3. LANE LOGIC (V4)
- MaskMode：2
- MaxCov：0.65
- MaskPx：250
- YelPx：250
- ROI Min：60
- BandH：90
- PeakMin：6
- LaneWMin：40

#### B4. STEERING (V4)
- Gain：2.40
- Limit：70
- Timeout：0.70
- Coast：0.55

#### B5. WHITE HSV（保留參數；黃線時通常不主用）
- H 色相：0 / 180
- S 飽和：0 / 60
- V 明度：180 / 255

#### B6. YELLOW HSV（黃線模式）
- H 色相：15 / 45
- S 飽和：60 / 255
- V 明度：80 / 255

#### B7. 已知現象與對策（黃線）
- 彎前變慢/停住（通常是「線道有效性不足」或「遮罩不穩」導致）：優先調整 YELLOW HSV（特別是 S/V）、並檢查 ROI Min 是否過高或 BandH 是否過窄，避免彎前線段落入 ROI 之外。
- 彎道貼線或過衝：可嘗試 LookAhead↑（增加前視）、或 Gain↓、或 CurveSlow↑（彎道降速更明顯）。
- 直線飄移：可微調 LaneWidth、或適度提高 Kd（但避免反應太遲鈍）。

---

## 備註
- 影片對照：請見 `data/videos/`
- 操作方式：請見 `INSTRUCTION.md`
- 主程式：`src/main.py`（保留原始檔：`src/play8_final_home_school_v5_Ultimate_Tuned.py`）
