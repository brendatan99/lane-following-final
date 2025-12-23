import cv2
import time
import numpy as np
import threading
import datetime
import libcamera
import traceback
import sys
import os
import json
from picamera2 import Picamera2
from flask import Flask, Response, render_template_string, jsonify, request

# ------------------------------------------------------------------
#  LOBOROBOT 初始化
# ------------------------------------------------------------------
from LOBOROBOT2 import LOBOROBOT
clbrobot = LOBOROBOT()
clbrobot.t_stop(0.1)

# ------------------------------------------------------------------
#  全域變數
# ------------------------------------------------------------------
ww, hh = 320, 240
Cam_X, Cam_Y = 10, 9
angle_pan = 90
angle_tilt = 15

running = True
mode = "stop"
latest_frame = None
latest_frame_time = 0.0
processed_frame = None 

is_recording = False
video_writer = None
SETTINGS_FILE = "user_params.json" 

frame_lock = threading.Lock()
param_lock = threading.Lock()

# ------------------------------------------------------------------
#  參數設定 (V4 完整版核心)
# ------------------------------------------------------------------
PARAMS = {
    # --- [動力 & PID] ---
    "speed_base": 50,
    "Kp": 0.45,
    "Kd": 0.30,
    "curve_slow": 0.45,

    # --- [白線 HSV] ---
    "h_min": 0,   "h_max": 180,
    "s_min": 0,   "s_max": 60,
    "v_min": 180, "v_max": 255,

    # --- [黃線 HSV] ---
    "yh_min": 15,  "yh_max": 45,
    "ys_min": 60,  "ys_max": 255,
    "yv_min": 80,  "yv_max": 255,

    # --- [遮罩邏輯] ---
    "mask_mode": 0,
    "mask_max_cov": 0.65,
    "min_mask_px": 250,
    "y_min_pixels": 250,
    "roi_y_min": 60,
    "band_h": 90,
    "peak_min": 6,
    "min_lane_width": 40,

    # --- [轉向控制] ---
    "steer_gain": 2.4,
    "steer_limit": 70,
    "lost_timeout": 0.7,
    "coast_factor": 0.55,

    # --- [S彎與優化] ---
    "s_lookahead": 0,
    "single_lane_width": 160,
    "white_curve_boost": 1.0,
    "white_line_thick": 1,

    # --- 遙測數據 ---
    "cte": 0.0, "fps": 0, "mask_used": 0, "steering": 0.0,
    "mask_px": 0, "mask_w_px": 0, "mask_y_px": 0
}

LANE_LAST_CENTER = ww // 2
LANE_LAST_WIDTH = 160

# ------------------------------------------------------------------
#  【基礎設定】(Factory Defaults) - 您的安全網
#  這些參數是我根據您的描述與 V4 設定調校好的最佳值
# ------------------------------------------------------------------
FACTORY_PRESETS = {
    "home": {
        # [模式] 家用=黃線
        "mask_mode": 2, 
        
        # [黃線 HSV] 針對室內黃色膠帶優化
        "yh_min": 15, "yh_max": 45, "ys_min": 60, "ys_max": 255, "yv_min": 80, "yv_max": 255,
        # [白線 HSV] 預設值
        "h_min": 0, "h_max": 180, "s_min": 0, "s_max": 60, "v_min": 180, "v_max": 255,

        # [動力] 標準速度 50，過彎減速 0.45
        "speed_base": 50, "Kp": 0.45, "Kd": 0.30, "curve_slow": 0.45,
        
        # [轉向] 靈敏度 2.4，限制 70
        "steer_gain": 2.4, "steer_limit": 70, "lost_timeout": 0.7, "coast_factor": 0.55,
        
        # [細節]
        "band_h": 90, "peak_min": 6, "min_lane_width": 40, "min_mask_px": 250, "y_min_pixels": 250,
        "white_curve_boost": 1.0, "s_lookahead": 0, "single_lane_width": 160, "roi_y_min": 60, "mask_max_cov": 0.65
    },
    "school": {
        # [模式] 學校=白線
        "mask_mode": 1, 
        
        # [白線 HSV] 針對學校白線優化 (低飽和度抗反光)
        "h_min": 0, "h_max": 180, "s_min": 0, "s_max": 40, "v_min": 180, "v_max": 255,
        # [黃線 HSV] 預設值
        "yh_min": 15, "yh_max": 45, "ys_min": 60, "ys_max": 255, "yv_min": 80, "yv_max": 255,

        # [動力] 速度 50，過彎減速 0.50 (學校彎道可能較急)
        "speed_base": 50, "Kp": 0.45, "Kd": 0.30, "curve_slow": 0.50,
        
        # [轉向]
        "steer_gain": 2.4, "steer_limit": 70, "lost_timeout": 0.7, "coast_factor": 0.55,
        
        # [細節] Boost 開啟以對抗白線對比度低
        "white_curve_boost": 1.2, "s_lookahead": 10, 
        "band_h": 90, "peak_min": 6, "min_lane_width": 40, "min_mask_px": 250, "y_min_pixels": 250,
        "single_lane_width": 160, "roi_y_min": 60, "mask_max_cov": 0.65
    }
}

# ------------------------------------------------------------------
#  參數管理邏輯 (雙層記憶)
# ------------------------------------------------------------------
def load_user_presets():
    """讀取用戶儲存的參數 (user_params.json)"""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, 'r') as f: return json.load(f)
        except: pass
    return {} # 如果沒有檔案，回傳空字典

def save_user_presets(preset_name, current_params):
    """將當前參數寫入用戶檔案"""
    data = load_user_presets()
    keys_to_save = list(PARAMS.keys())
    # 排除唯讀數據，只存設定值
    for k in ["cte", "fps", "mask_used", "steering", "mask_px", "mask_w_px", "mask_y_px", "left_spd", "right_spd"]:
        if k in keys_to_save: keys_to_save.remove(k)
            
    if preset_name not in data: data[preset_name] = {}
    for k in keys_to_save:
        if k in current_params: data[preset_name][k] = current_params[k]
            
    with open(SETTINGS_FILE, 'w') as f: json.dump(data, f, indent=4)

# ------------------------------------------------------------------
#  HTML 介面 (加入快捷鍵監聽與新按鍵)
# ------------------------------------------------------------------
INDEX_HTML = r"""
<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Mini Cooper 2025 Xmas</title>
  <link href="https://fonts.googleapis.com/css2?family=Varela+Round&display=swap" rel="stylesheet">
  <style>
    :root { 
        --bg-snow: #eef2f3;
        --mini-pink: #ffadd2;
        --mini-dark-pink: #ff7eb9;
        --xmas-red: #d42426;
        --xmas-green: #165b33;
        --text-color: #2c3e50;
    }
    
    body { 
        background-color: var(--bg-snow);
        background-image: radial-gradient(#fff 2px, transparent 2.5px);
        background-size: 30px 30px;
        color: var(--text-color); 
        font-family: 'Varela Round', sans-serif; 
        margin: 0; padding: 10px;
    }

    .racing-stripe { position: fixed; top: 0; bottom: 0; width: 40px; background: var(--mini-pink); opacity: 0.15; z-index: -2; }
    .stripe-left { left: 15%; border-right: 5px solid #fff; }
    .stripe-right { right: 15%; border-left: 5px solid #fff; }

    /* Command Center */
    .command-center {
        display: flex; flex-wrap: wrap; justify-content: center; align-items: center;
        background: #fff; padding: 10px; border-radius: 20px;
        box-shadow: 0 5px 20px rgba(0,0,0,0.08);
        border: 2px solid var(--mini-pink);
        margin-bottom: 15px; gap: 20px; 
        max-width: 1400px; margin-left: auto; margin-right: auto;
    }

    .dpad-container { display: grid; grid-template-columns: 40px 40px 40px; gap: 4px; }
    .dpad-btn {
        width: 40px; height: 40px; border-radius: 50%; border: none;
        background: var(--mini-dark-pink); color: #fff; font-size: 18px;
        cursor: pointer; box-shadow: 0 3px 0 #c25e8a; display: flex; align-items: center; justify-content: center;
    }
    .dpad-btn:active { transform: translateY(3px); box-shadow: none; }

    .header-group { text-align: center; }
    .title-row { 
        font-size: 28px; font-weight: bold; color: var(--xmas-green); 
        margin-bottom: 5px; display: flex; align-items: center; justify-content: center; gap: 15px;
    }
    .deco-icon { font-size: 24px; } 

    .dashboard { display: flex; gap: 10px; justify-content: center; }
    .dial {
        width: 65px; height: 65px; background: #fdfdfd; border: 3px solid var(--mini-pink);
        border-radius: 50%; display: flex; flex-direction: column; align-items: center; justify-content: center;
        box-shadow: 0 3px 5px rgba(0,0,0,0.05);
    }
    .dial-val { font-size: 16px; font-weight: bold; color: var(--xmas-red); }
    .dial-lbl { font-size: 9px; color: #888; }

    .control-group { display: flex; flex-direction: column; gap: 6px; min-width: 320px; }
    .btn-row { display: flex; gap: 6px; width: 100%; }
    .btn {
        flex: 1; padding: 10px; border: none; border-radius: 12px; color: #fff; font-weight: bold; cursor: pointer;
        font-size: 13px; box-shadow: 0 3px 0 rgba(0,0,0,0.2); transition: transform 0.1s;
        display: flex; align-items: center; justify-content: center;
    }
    .btn:active { transform: translateY(3px); box-shadow: none; }
    
    .btn-start { background: linear-gradient(135deg, #27ae60, #1e8449); font-size: 16px; }
    .btn-stop { background: linear-gradient(135deg, #c0392b, #922b21); font-size: 16px; }
    
    /* 上次設定 (用戶) */
    .btn-user-y { background: linear-gradient(135deg, #f39c12, #d35400); } 
    .btn-user-w { background: linear-gradient(135deg, #7f8c8d, #2c3e50); }
    
    /* 基礎設定 (原廠) */
    .btn-factory-y { background: linear-gradient(135deg, #f1c40f, #f39c12); color: #333; } 
    .btn-factory-w { background: linear-gradient(135deg, #bdc3c7, #95a5a6); color: #333; }

    .btn-save { background: linear-gradient(135deg, #9b59b6, #8e44ad); font-size: 12px; flex: 0.6; }
    .btn-rec { background: linear-gradient(135deg, #ff758c, #ff7eb3); }
    .btn-off { background: linear-gradient(135deg, #34495e, #2c3e50); }

    .main-content {
        display: grid; grid-template-columns: 1fr 400px; gap: 15px;
        max-width: 1400px; margin: 0 auto;
    }
    @media (max-width: 950px) { .main-content { grid-template-columns: 1fr; } }

    .card {
        background: rgba(255, 255, 255, 0.95); border-radius: 15px; padding: 15px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.05); border: 2px solid var(--mini-pink);
        position: relative; 
    }
    .card-title {
        font-size: 16px; color: var(--mini-dark-pink); margin-bottom: 10px; 
        border-bottom: 2px dashed var(--mini-pink); padding-bottom: 5px; font-weight: bold;
    }

    .cam-frame { width: 100%; border-radius: 10px; background: #000; display: block; }
    .capsule-row { display: flex; gap: 5px; margin-top: 5px; }
    .btn-view {
        flex:1; padding: 8px; border-radius: 20px; border: none; background: #eee; 
        font-weight: bold; cursor: pointer; color: #555;
    }
    .btn-view.active { background: var(--mini-pink); color: #fff; }

    .param-section { margin-bottom: 8px; background: #fff0f5; padding: 8px; border-radius: 10px; }
    .slider-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; }
    .slider-lbl { font-size: 11px; color: #666; width: 45%; }
    .slider-val { font-size: 11px; color: var(--mini-dark-pink); font-weight: bold; width: 15%; text-align: right; }
    input[type=range] { width: 40%; }

    /* HSV 工業化介面專用 CSS */
    .hsv-row { display: flex; align-items: center; margin-bottom: 5px; }
    .hsv-label { font-size: 11px; color: #333; width: 15%; font-weight:bold; }
    .hsv-slider { width: 32%; margin: 0 2px; }
    .hsv-val { font-size: 11px; color: var(--mini-dark-pink); width: 18%; text-align: right; font-weight: bold; }

    .rec-indicator {
        position: absolute; top: 50px; right: 25px;
        background-color: rgba(0, 0, 0, 0.6);
        color: #ff3b30; font-weight: bold; font-size: 14px;
        padding: 5px 10px; border-radius: 5px;
        display: none; align-items: center; gap: 5px;
        z-index: 100; pointer-events: none;
    }
    .rec-dot {
        width: 10px; height: 10px; background-color: #ff3b30; border-radius: 50%;
        animation: blink 1s infinite;
    }
    @keyframes blink { 50% { opacity: 0; } }

    .status-light { width: 12px; height: 12px; background: #ccc; border-radius: 50%; display: inline-block; margin-left:5px;}
    .status-ok { background: #2ecc71; box-shadow: 0 0 8px #2ecc71; }

  </style>
</head>
<body>

<div class="racing-stripe stripe-left"></div>
<div class="racing-stripe stripe-right"></div>

<div class="command-center">
    <div style="text-align:center;">
        <div style="font-size:10px; color:#999; margin-bottom:3px;">CAM</div>
        <div class="dpad-container">
            <div></div><button class="dpad-btn" onclick="post('/api/cam/up')">▲</button><div></div>
            <button class="dpad-btn" onclick="post('/api/cam/left')">◀</button>
            <button class="dpad-btn" onclick="post('/api/cam/center')">●</button>
            <button class="dpad-btn" onclick="post('/api/cam/right')">▶</button>
            <div></div><button class="dpad-btn" onclick="post('/api/cam/down')">▼</button><div></div>
        </div>
    </div>

    <div class="header-group">
        <div class="title-row">
            <span class="deco-icon">🎄</span>
            <span class="deco-icon">🎅</span>
            <span>Mini Cooper 2025 Xmas</span>
            <span class="deco-icon">⛄</span>
            <span class="deco-icon">🎁</span>
            <span id="status-light" class="status-light"></span>
        </div>
        <div class="dashboard">
            <div class="dial"><div class="dial-val" id="d-spd">0</div><div class="dial-lbl">SPEED</div></div>
            <div class="dial"><div class="dial-val" id="d-steer">0</div><div class="dial-lbl">STEER</div></div>
            <div class="dial"><div class="dial-val" id="d-cte">0.0</div><div class="dial-lbl">CTE</div></div>
            <div class="dial"><div class="dial-val" id="d-fps">0</div><div class="dial-lbl">FPS</div></div>
        </div>
        <div style="font-size:10px; color:#999; margin-top:5px;">(緊急煞車快捷鍵: 空白鍵 Space 或 S)</div>
    </div>

    <div class="control-group">
        <div class="btn-row">
            <button class="btn btn-start" onclick="post('/api/mode/start')">START</button>
            <button class="btn btn-stop" onclick="post('/api/mode/stop')">STOP</button>
        </div>
        <div class="btn-row">
            <button class="btn btn-user-y" onclick="setPreset('user', 'home')">📂 上次設定 (黃線)</button>
            <button class="btn btn-save" onclick="savePreset('home')">💾 存自設黃</button>
        </div>
        <div class="btn-row">
            <button class="btn btn-user-w" onclick="setPreset('user', 'school')">📂 上次設定 (白線)</button>
            <button class="btn btn-save" onclick="savePreset('school')">💾 存自設白</button>
        </div>
        <div class="btn-row">
            <button class="btn btn-factory-y" onclick="setPreset('factory', 'home')">🏭 基礎設定 (黃線)</button>
            <button class="btn btn-factory-w" onclick="setPreset('factory', 'school')">🏭 基礎設定 (白線)</button>
        </div>
        <div class="btn-row">
            <button class="btn btn-rec" onclick="post('/api/rec/toggle')">錄影</button>
            <button class="btn btn-off" onclick="shutdown()">關機</button>
        </div>
    </div>
</div>

<div class="main-content">
    <div class="left-col">
        <div class="card">
            <div class="card-title">📷 LIVE VIEW</div>
            <div id="rec-indicator" class="rec-indicator">
                <div class="rec-dot"></div> REC
            </div>
            <img id="video" class="cam-frame" src="/live_view?m=cv">
            <div class="capsule-row">
                <button class="btn-view active" onclick="src('cv',this)">原始畫面</button>
                <button class="btn-view" onclick="src('mask',this)">遮罩</button>
                <button class="btn-view" onclick="src('maskw',this)">白線</button>
                <button class="btn-view" onclick="src('masky',this)">黃線</button>
            </div>
        </div>
    </div>

    <div class="right-col">
        <div class="card">
            <div class="card-title" id="tuning-title">🎁 TUNING (V4 完整版)</div>
            
            <div class="param-section">
                <div style="font-size:10px; color:#888;">POWER & PID</div>
                <div class="slider-row"><span class="slider-lbl">Speed</span><input id="in-speed_base" type="range" max="80" value="50" oninput="upd('speed_base',this.value)"><span class="slider-val" id="v-speed_base">50</span></div>
                <div class="slider-row"><span class="slider-lbl">Kp (Turn)</span><input id="in-Kp" type="range" max="2" step="0.01" value="0.45" oninput="upd('Kp',this.value)"><span class="slider-val" id="v-Kp">0.45</span></div>
                <div class="slider-row"><span class="slider-lbl">Kd (Stable)</span><input id="in-Kd" type="range" max="2" step="0.01" value="0.30" oninput="upd('Kd',this.value)"><span class="slider-val" id="v-Kd">0.30</span></div>
                <div class="slider-row"><span class="slider-lbl">CurveSlow</span><input id="in-curve_slow" type="range" max="0.9" step="0.05" value="0.45" oninput="upd('curve_slow',this.value)"><span class="slider-val" id="v-curve_slow">0.45</span></div>
            </div>

            <div class="param-section" style="background:#e8f6f3;">
                <div style="font-size:10px; color:var(--xmas-green);">S-CURVE & OPTION</div>
                <div class="slider-row"><span class="slider-lbl">LookAhead</span><input id="in-s_lookahead" type="range" min="-20" max="40" step="1" value="0" oninput="upd('s_lookahead',this.value)"><span class="slider-val" id="v-s_lookahead">0</span></div>
                <div class="slider-row"><span class="slider-lbl">LaneWidth</span><input id="in-single_lane_width" type="range" min="80" max="250" step="5" value="160" oninput="upd('single_lane_width',this.value)"><span class="slider-val" id="v-single_lane_width">160</span></div>
                <div class="slider-row"><span class="slider-lbl">Boost</span><input id="in-white_curve_boost" type="range" min="1.0" max="2.0" step="0.1" value="1.0" oninput="upd('white_curve_boost',this.value)"><span class="slider-val" id="v-white_curve_boost">1.0</span></div>
            </div>

            <div class="param-section">
                <div style="font-size:10px; color:#888;">LANE LOGIC (V4)</div>
                <div class="slider-row"><span class="slider-lbl">MaskMode</span><input id="in-mask_mode" type="range" max="3" value="0" oninput="upd('mask_mode',this.value)"><span class="slider-val" id="v-mask_mode">0</span></div>
                <div class="slider-row"><span class="slider-lbl">MaxCov</span><input id="in-mask_max_cov" type="range" min="0.1" max="1.0" step="0.05" value="0.65" oninput="upd('mask_max_cov',this.value)"><span class="slider-val" id="v-mask_max_cov">0.65</span></div>
                <div class="slider-row"><span class="slider-lbl">MaskPx</span><input id="in-min_mask_px" type="range" max="1000" value="250" oninput="upd('min_mask_px',this.value)"><span class="slider-val" id="v-min_mask_px">250</span></div>
                <div class="slider-row"><span class="slider-lbl">YelPx</span><input id="in-y_min_pixels" type="range" max="1000" value="250" oninput="upd('y_min_pixels',this.value)"><span class="slider-val" id="v-y_min_pixels">250</span></div>
                <div class="slider-row"><span class="slider-lbl">ROI Min</span><input id="in-roi_y_min" type="range" max="200" value="60" oninput="upd('roi_y_min',this.value)"><span class="slider-val" id="v-roi_y_min">60</span></div>
                <div class="slider-row"><span class="slider-lbl">BandH</span><input id="in-band_h" type="range" max="140" value="90" oninput="upd('band_h',this.value)"><span class="slider-val" id="v-band_h">90</span></div>
                <div class="slider-row"><span class="slider-lbl">PeakMin</span><input id="in-peak_min" type="range" max="50" value="6" oninput="upd('peak_min',this.value)"><span class="slider-val" id="v-peak_min">6</span></div>
                <div class="slider-row"><span class="slider-lbl">LaneWMin</span><input id="in-min_lane_width" type="range" max="100" value="40" oninput="upd('min_lane_width',this.value)"><span class="slider-val" id="v-min_lane_width">40</span></div>
            </div>

            <div class="param-section">
                <div style="font-size:10px; color:#888;">STEERING (V4)</div>
                <div class="slider-row"><span class="slider-lbl">Gain</span><input id="in-steer_gain" type="range" max="5.0" step="0.1" value="2.4" oninput="upd('steer_gain',this.value)"><span class="slider-val" id="v-steer_gain">2.4</span></div>
                <div class="slider-row"><span class="slider-lbl">Limit</span><input id="in-steer_limit" type="range" max="100" value="70" oninput="upd('steer_limit',this.value)"><span class="slider-val" id="v-steer_limit">70</span></div>
                <div class="slider-row"><span class="slider-lbl">Timeout</span><input id="in-lost_timeout" type="range" max="2.0" step="0.1" value="0.7" oninput="upd('lost_timeout',this.value)"><span class="slider-val" id="v-lost_timeout">0.7</span></div>
                <div class="slider-row"><span class="slider-lbl">Coast</span><input id="in-coast_factor" type="range" max="1.0" step="0.05" value="0.55" oninput="upd('coast_factor',this.value)"><span class="slider-val" id="v-coast_factor">0.55</span></div>
            </div>

            <div class="param-section">
                <div style="font-size:10px; color:#888; margin-bottom:5px;">WHITE HSV</div>
                
                <div class="hsv-row">
                    <span class="hsv-label">H 色相</span>
                    <input id="in-h_min" class="hsv-slider" type="range" max="180" value="0" oninput="upd('h_min',this.value)">
                    <input id="in-h_max" class="hsv-slider" type="range" max="180" value="180" oninput="upd('h_max',this.value)">
                    <span class="hsv-val"><span id="v-h_min">0</span>/<span id="v-h_max">180</span></span>
                </div>
                
                <div class="hsv-row">
                    <span class="hsv-label">S 飽和</span>
                    <input id="in-s_min" class="hsv-slider" type="range" max="255" value="0" oninput="upd('s_min',this.value)">
                    <input id="in-s_max" class="hsv-slider" type="range" max="255" value="60" oninput="upd('s_max',this.value)">
                    <span class="hsv-val"><span id="v-s_min">0</span>/<span id="v-s_max">60</span></span>
                </div>

                <div class="hsv-row">
                    <span class="hsv-label">V 明度</span>
                    <input id="in-v_min" class="hsv-slider" type="range" max="255" value="180" oninput="upd('v_min',this.value)">
                    <input id="in-v_max" class="hsv-slider" type="range" max="255" value="255" oninput="upd('v_max',this.value)">
                    <span class="hsv-val"><span id="v-v_min">180</span>/<span id="v-v_max">255</span></span>
                </div>
            </div>

            <div class="param-section">
                <div style="font-size:10px; color:#888; margin-bottom:5px;">YELLOW HSV</div>
                
                <div class="hsv-row">
                    <span class="hsv-label">H 色相</span>
                    <input id="in-yh_min" class="hsv-slider" type="range" max="180" value="15" oninput="upd('yh_min',this.value)">
                    <input id="in-yh_max" class="hsv-slider" type="range" max="180" value="45" oninput="upd('yh_max',this.value)">
                    <span class="hsv-val"><span id="v-yh_min">15</span>/<span id="v-yh_max">45</span></span>
                </div>
                
                <div class="hsv-row">
                    <span class="hsv-label">S 飽和</span>
                    <input id="in-ys_min" class="hsv-slider" type="range" max="255" value="60" oninput="upd('ys_min',this.value)">
                    <input id="in-ys_max" class="hsv-slider" type="range" max="255" value="255" oninput="upd('ys_max',this.value)">
                    <span class="hsv-val"><span id="v-ys_min">60</span>/<span id="v-ys_max">255</span></span>
                </div>

                <div class="hsv-row">
                    <span class="hsv-label">V 明度</span>
                    <input id="in-yv_min" class="hsv-slider" type="range" max="255" value="80" oninput="upd('yv_min',this.value)">
                    <input id="in-yv_max" class="hsv-slider" type="range" max="255" value="255" oninput="upd('yv_max',this.value)">
                    <span class="hsv-val"><span id="v-yv_min">80</span>/<span id="v-yv_max">255</span></span>
                </div>
            </div>

        </div>
    </div>
</div>

<script>
function src(m,b){ document.getElementById('video').src=`/live_view?m=${m}&t=${Date.now()}`; document.querySelectorAll('.capsule-row .btn-view').forEach(x=>x.classList.remove('active')); if(b)b.classList.add('active'); }

function post(u,b){ 
    fetch(u,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(b||{})})
    .catch(err => console.error("API Fail:", err));
}

function upd(k,v){ 
    let el = document.getElementById('v-'+k);
    if(el) el.innerText=v; 
    let o={}; 
    o[k]=(['Kp','Kd','curve_slow','mask_max_cov','steer_gain','lost_timeout','coast_factor','white_curve_boost'].includes(k)) ? parseFloat(v) : parseInt(v); 
    post('/api/params',o); 
}

// 核心功能：讀取參數 (支援 User 與 Factory 模式)
async function setPreset(type, mode) {
    let url = (type === 'factory') ? ('/api/preset/factory/' + mode) : ('/api/preset/user/' + mode);
    try {
        let res = await fetch(url, {method:'POST'});
        let j = await res.json();
        if(j.ok) {
            // 立刻更新介面
            let hudRes = await fetch('/api/hud');
            let d = await hudRes.json();
            updateUI(d, true);
            
            let titleEl = document.getElementById('tuning-title');
            let label = (mode === 'home') ? '黃線' : '白線';
            let source = (type === 'factory') ? '基礎設定' : '上次設定';
            titleEl.innerHTML = `🎁 TUNING (${source} - ${label})`;
        } else {
            if(type === 'user') alert("找不到上次設定，請先儲存一次！");
        }
    } catch(e) { alert("連線錯誤"); }
}

async function savePreset(mode) {
    if(!confirm("確定要儲存當前所有參數嗎？\n這將覆蓋 [上次設定] 的紀錄。")) return;
    try {
        let res = await fetch('/api/save_preset/'+mode, {method:'POST'});
        let j = await res.json();
        if(j.ok) alert("儲存成功！");
        else alert("儲存失敗。");
    } catch(e) { alert("連線錯誤"); }
}

function shutdown() {
    if(confirm("確定要關閉樹莓派嗎？(sudo shutdown -h now)")) {
        post('/api/shutdown');
        alert("正在關機... 請稍候 20 秒再拔電源。");
    }
}

function updateUI(d, force) {
    if(d.speed_base !== undefined) document.getElementById('d-spd').innerText = d.speed_base;
    if(d.steering !== undefined) document.getElementById('d-steer').innerText = (d.steering).toFixed(0);
    if(d.cte !== undefined) document.getElementById('d-cte').innerText = (d.cte).toFixed(1);
    if(d.fps !== undefined) document.getElementById('d-fps').innerText = d.fps;

    let light = document.getElementById('status-light');
    if(light) {
        if(d.fps > 0) light.classList.add('status-ok');
        else light.classList.remove('status-ok');
    }

    // 錄影燈
    let recEl = document.getElementById('rec-indicator');
    if(recEl) recEl.style.display = (d.recording) ? 'flex' : 'none';

    for (const [key, value] of Object.entries(d)) {
        let txtEl = document.getElementById('v-'+key);
        if(txtEl) txtEl.innerText = value;
        if (force) {
            let inputEl = document.getElementById('in-'+key);
            if(inputEl) inputEl.value = value;
        }
    }
}

// 監聽鍵盤 (空白鍵 或 S 鍵) 進行緊急煞車
document.addEventListener('keydown', function(event) {
    if (event.key === " " || event.key === "s" || event.key === "S") {
        post('/api/mode/stop');
    }
});

async function loop(){
 try{
  let res = await fetch('/api/hud');
  let d = await res.json();
  updateUI(d, false); 
 }catch(e){}
 setTimeout(loop, 250);
}
loop();
</script>
</body>
</html>
"""

# ------------------------------------------------------------------
#  核心控制邏輯
# ------------------------------------------------------------------
def _motor_stop(): clbrobot.t_stop(0.02)

last_l_sent, last_r_sent = -999, -999
def _motor_drive(l, r):
    global last_l_sent, last_r_sent
    if l != last_l_sent or r != last_r_sent:
        clbrobot.MotorRun(0, "forward", l); clbrobot.MotorRun(2, "forward", l)
        clbrobot.MotorRun(1, "forward", r); clbrobot.MotorRun(3, "forward", r)
        last_l_sent, last_r_sent = l, r

def control_core():
    global latest_frame, latest_frame_time, processed_frame, mode, running
    global LANE_LAST_CENTER, LANE_LAST_WIDTH

    pid_error_last = 0.0
    first_lock = True
    lost_start = None
    last_steer = 0.0
    last_lane_ok = False
    local_frame_time = 0.0 
    fps_cnt = 0; fps_tm = time.time()

    while running:
        try:
            frame = None
            with frame_lock:
                if latest_frame is None:
                    time.sleep(0.002)
                    continue
                if latest_frame_time == local_frame_time:
                    time.sleep(0.001)
                    continue
                frame = latest_frame.copy()
                local_frame_time = latest_frame_time

            with param_lock:
                speed_base = float(PARAMS["speed_base"])
                kp = float(PARAMS["Kp"]); kd = float(PARAMS["Kd"])
                curve_slow = float(PARAMS["curve_slow"])
                mask_mode = int(PARAMS["mask_mode"])
                max_cov = float(PARAMS["mask_max_cov"])
                y_min_px = int(PARAMS["y_min_pixels"])
                s_lookahead = int(PARAMS.get("s_lookahead", 0))
                single_lane_w = int(PARAMS.get("single_lane_width", 160)) 
                white_thick = int(PARAMS.get("white_line_thick", 1))
                white_boost = float(PARAMS.get("white_curve_boost", 1.0))
                roi_y = max(0, min(hh-10, int(PARAMS["roi_y_min"]) + s_lookahead))
                
                lw = np.array([PARAMS["h_min"], PARAMS["s_min"], PARAMS["v_min"]], dtype=np.uint8)
                uw = np.array([PARAMS["h_max"], PARAMS["s_max"], PARAMS["v_max"]], dtype=np.uint8)
                ly = np.array([PARAMS["yh_min"], PARAMS["ys_min"], PARAMS["yv_min"]], dtype=np.uint8)
                uy = np.array([PARAMS["yh_max"], PARAMS["ys_max"], PARAMS["yv_max"]], dtype=np.uint8)
                
                band_h = int(PARAMS["band_h"])
                peak_min = int(PARAMS["peak_min"])
                min_lane_w = int(PARAMS["min_lane_width"])
                steer_gain = float(PARAMS["steer_gain"])
                steer_lim = float(PARAMS["steer_limit"])

            roi = frame[roi_y:hh, 0:ww]
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            mask_w = cv2.inRange(hsv, lw, uw)
            mask_y = cv2.inRange(hsv, ly, uy)
            
            w_px = mask_w.sum() // 255; y_px = mask_y.sum() // 255
            roi_px = mask_w.shape[0] * mask_w.shape[1]
            used = 0; is_white = False

            if mask_mode == 1: mask = mask_w; used = 1; is_white = True
            elif mask_mode == 2: mask = mask_y; used = 2
            elif mask_mode == 3: mask = cv2.bitwise_or(mask_w, mask_y); used = 3
            else:
                if (w_px/max(1,roi_px) > max_cov and y_px >= y_min_px) or (y_px >= y_min_px and y_px < w_px):
                    mask = mask_y; used = 2
                else:
                    mask = mask_w; used = 1; is_white = True

            if (mask.sum()//255)/max(1,roi_px) > max_cov and used!=2 and y_px>=y_min_px:
                mask = mask_y; used = 2

            if is_white and white_thick > 0:
                mask = cv2.dilate(mask, np.ones((3,3),np.uint8), iterations=white_thick)

            mask_clean = mask
            if (mask.sum()//255) > 1200:
                mask_clean = cv2.morphologyEx(mask_clean, cv2.MORPH_OPEN, np.ones((3,3),np.uint8), iterations=1)
            mask_clean = cv2.morphologyEx(mask_clean, cv2.MORPH_CLOSE, np.ones((3,3),np.uint8), iterations=1)

            band = mask_clean[-band_h:, :]
            hist = np.sum(band > 0, axis=0)
            
            mid = ww // 2
            lx = None; rx = None
            if hist[:mid].max() >= peak_min: lx = int(np.argmax(hist[:mid]))
            if hist[mid:].max() >= peak_min: rx = int(np.argmax(hist[mid:]) + mid)

            has_line = False
            lane_center = LANE_LAST_CENTER
            current_lane_width = LANE_LAST_WIDTH 

            if used != 0:
                if lx is not None and rx is not None and (rx - lx) > min_lane_w:
                    lane_center = (lx + rx) // 2
                    current_lane_width = rx - lx 
                    has_line = True
                elif lx is not None:
                    lane_center = lx + (current_lane_width // 2) 
                    has_line = True
                elif rx is not None:
                    lane_center = rx - (current_lane_width // 2)
                    has_line = True
            
            if has_line:
                lane_center = int(max(0, min(ww-1, lane_center)))
                LANE_LAST_WIDTH = int(current_lane_width) 
                LANE_LAST_CENTER = lane_center

            cte = float(mid - lane_center) if has_line else 0.0
            if is_white and abs(cte) > 10: cte *= white_boost

            # 視覺化
            y_vis = roi.shape[0] - (band_h // 2)
            if lx: cv2.circle(roi, (lx, y_vis), 5, (0,255,0), -1)
            if rx: cv2.circle(roi, (rx, y_vis), 5, (0,255,0), -1)
            cv2.circle(roi, (lane_center, y_vis), 6, (255,0,0), -1)
            cv2.line(roi, (mid, y_vis-15), (mid, y_vis+15), (0,255,255), 2)

            processed_frame = {
                "cv": frame, 
                "mask": cv2.cvtColor(mask_clean, cv2.COLOR_GRAY2BGR),
                "maskw": cv2.cvtColor(mask_w, cv2.COLOR_GRAY2BGR), 
                "masky": cv2.cvtColor(mask_y, cv2.COLOR_GRAY2BGR)
            }
            
            with param_lock:
                PARAMS["cte"] = cte
                PARAMS["mask_used"] = used
                PARAMS["mask_px"] = int(mask_clean.sum()//255)

            if is_recording and video_writer: 
                try: video_writer.write(cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                except: pass

            if mode == "auto":
                with param_lock:
                    to = float(PARAMS["lost_timeout"]); cf = float(PARAMS["coast_factor"])
                    mm_px = int(PARAMS["min_mask_px"])
                
                if has_line and (mask_clean.sum()//255) < mm_px: has_line = False

                if not has_line:
                    first_lock = True
                    if lost_start is None: lost_start = time.time()
                    if last_lane_ok and (time.time() - lost_start) <= to:
                        base = max(0, min(100, speed_base * cf))
                        st = max(-steer_lim, min(steer_lim, last_steer))
                        l = int(max(0, min(100, base - st)))
                        r = int(max(0, min(100, base + st)))
                        _motor_drive(l, r)
                        with param_lock: PARAMS["steering"] = st
                    else:
                        _motor_stop(); mode="stop"; last_lane_ok=False
                        with param_lock: PARAMS["steering"] = 0
                else:
                    err = cte
                    if abs(err) < 2.0: err = 0.0

                    if first_lock:
                        pid_error_last = err
                        first_lock = False
                        
                    derr = err - pid_error_last
                    
                    raw_st = (kp * err) + (kd * derr)
                    pid_error_last = err
                    
                    raw_st *= steer_gain
                    raw_st = max(-steer_lim, min(steer_lim, raw_st))
                    
                    st = (0.6 * raw_st) + (0.4 * last_steer)

                    sf = 1.0 - (curve_slow * min(1.0, abs(st)/steer_lim))
                    base = max(0.0, min(100.0, speed_base * sf))
                    
                    l = int(max(0, min(100, base - st)))
                    r = int(max(0, min(100, base + st)))
                    
                    lost_start = None; last_lane_ok = True; last_steer = st
                    _motor_drive(l, r)
                    with param_lock: PARAMS["steering"] = st
            else:
                _motor_stop(); pid_error_last=0.0; first_lock=True
                with param_lock: PARAMS["steering"] = 0
            
            fps_cnt += 1
            if time.time()-fps_tm >= 1.0:
                with param_lock: PARAMS["fps"] = fps_cnt
                fps_cnt=0; fps_tm=time.time()

        except Exception as e:
            print(f"Error in control_core: {e}")
            traceback.print_exc()
            time.sleep(1)

# ------------------------------------------------------------------
#  Flask & Camera
# ------------------------------------------------------------------
picamera = Picamera2()
cfg = picamera.create_preview_configuration(main={"format":"RGB888", "size":(ww,hh)})
cfg["transform"] = libcamera.Transform(hflip=1, vflip=1)
picamera.configure(cfg); picamera.start()

def capture_loop():
    global latest_frame, latest_frame_time, running
    while running:
        frame = picamera.capture_array()
        if frame is not None:
            with frame_lock: 
                latest_frame = frame
                latest_frame_time = time.time()
        time.sleep(0.01)

threading.Thread(target=capture_loop, daemon=True).start()
threading.Thread(target=control_core, daemon=True).start()

app = Flask(__name__)
@app.route("/")
def index(): return render_template_string(INDEX_HTML)

def gen_frame(m):
    while True:
        out = None
        if processed_frame: out = processed_frame.get(m, processed_frame.get("cv"))
        if out is None:
            with frame_lock: 
                if latest_frame is not None: out = latest_frame.copy()
        if out is None: time.sleep(0.05); continue
        try:
            ret, jpeg = cv2.imencode(".jpg", cv2.cvtColor(out, cv2.COLOR_RGB2BGR))
            if ret: yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg.tobytes() + b"\r\n")
        except: pass
        time.sleep(0.04)

@app.route("/live_view")
def live_view(): return Response(gen_frame(request.args.get("m", "cv")), mimetype="multipart/x-mixed-replace; boundary=frame")

@app.route("/api/params", methods=["POST"])
def ap():
    with param_lock:
        for k,v in request.json.items(): 
            if k in PARAMS: PARAMS[k]=v
    return jsonify({"ok":True})

# ★★★ 雙模式載入 API ★★★
@app.route("/api/preset/<type>/<mode>", methods=["POST"])
def set_preset_api(type, mode):
    target_preset = {}
    
    if type == "factory":
        # 讀取寫死的原廠設定 (絕對安全)
        target_preset = FACTORY_PRESETS.get(mode)
    elif type == "user":
        # 讀取用戶自訂檔
        user_presets = load_user_presets()
        target_preset = user_presets.get(mode)
        if not target_preset:
            return jsonify({"ok":False, "msg":"No saved data"})
            
    if target_preset:
        with param_lock:
            for k,v in target_preset.items():
                PARAMS[k] = v
        return jsonify({"ok":True})
    return jsonify({"ok":False})

@app.route("/api/save_preset/<mode>", methods=["POST"])
def save_preset_endpoint(mode):
    with param_lock:
        current = PARAMS.copy()
    save_user_presets(mode, current)
    return jsonify({"ok":True})

@app.route("/api/hud")
def ah(): 
    with param_lock:
        # 傳送錄影狀態給前端
        data = PARAMS.copy()
        data["recording"] = is_recording
        return jsonify(data)

@app.route("/api/mode/<m>", methods=["POST"])
def am(m): global mode; mode="auto" if m=="start" else "stop"; return jsonify({"mode":mode})

@app.route("/api/cam/<a>", methods=["POST"])
def ac(a):
    global angle_pan, angle_tilt
    if a=="left": angle_pan-=5
    elif a=="right": angle_pan+=5
    elif a=="up": angle_tilt+=5
    elif a=="down": angle_tilt-=5
    elif a=="center": angle_pan=90; angle_tilt=15
    angle_pan=max(0,min(180,angle_pan)); angle_tilt=max(0,min(180,angle_tilt))
    clbrobot.set_servo_angle(Cam_X, angle_pan, 0.2); clbrobot.set_servo_angle(Cam_Y, angle_tilt, 0.2)
    return jsonify({})

@app.route("/api/rec/toggle", methods=["POST"])
def ar():
    global is_recording, video_writer
    if is_recording: is_recording=False; video_writer.release()
    else:
        fn = f"/home/pi119/Videos/race_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.avi"
        video_writer = cv2.VideoWriter(fn, cv2.VideoWriter_fourcc(*"XVID"), 20.0, (ww,hh))
        is_recording=True
    return jsonify({"r":is_recording})

@app.route("/api/shutdown", methods=["POST"])
def shutdown_pi():
    global running
    running = False
    _motor_stop()
    os.system("sudo shutdown -h now")
    return jsonify({"ok":True})

@app.route("/api/exit", methods=["POST"])
def ae(): global running; running=False; _motor_stop(); request.environ.get('werkzeug.server.shutdown')(); return jsonify({})

if __name__ == "__main__":
    clbrobot.set_servo_angle(Cam_X, angle_pan, 0.3); clbrobot.set_servo_angle(Cam_Y, angle_tilt, 0.3)
    app.run(host="0.0.0.0", port=5000, threaded=True, debug=False)