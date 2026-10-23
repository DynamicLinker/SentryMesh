import os
import shutil
import subprocess
import sys
import threading
import time

sys.path.insert(0, "/home/chadpenguin/Projects/AMAZON")
import uvicorn
from playwright.sync_api import sync_playwright

CHROME_EXEC = "/home/chadpenguin/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome"
FRAMES_DIR  = "/home/chadpenguin/Projects/AMAZON/video_frames"
RAW_VIDEO   = "/home/chadpenguin/Projects/AMAZON/raw_demo_video.mp4"

# Scene timing (seconds) aligned to voiceover clips:
#   clip_01 = 12.56s  -> Scene 1: intro card + overview
#   clip_02 = 14.40s  -> Scene 2: System 1 panel highlight
#   clip_03 = 12.96s  -> Scene 3: injection attack
#   clip_04 = 13.04s  -> Scene 4: verified courier
#   clip_05 = 11.20s  -> Scene 5: benchmark / audit tail

CAPTURE_FPS = 15
SCENE_DURATIONS = [12.56, 14.40, 12.96, 13.04, 11.20]

os.makedirs(FRAMES_DIR, exist_ok=True)

def run_srv():
    from sentrymesh.mcp.server import app
    uvicorn.run(app, host="127.0.0.1", port=8015, log_level="error")

srv = threading.Thread(target=run_srv, daemon=True)
srv.start()
print("[1/3] SentryMesh server listening on http://127.0.0.1:8015 ...")
time.sleep(2.0)

print("[2/3] Capturing browser frames at 1920x1080 @ 15fps ...")
frame_idx = 0

def capture_scene(page, duration_sec, label=""):
    global frame_idx
    total_frames = int(round(duration_sec * CAPTURE_FPS))
    interval = 1.0 / CAPTURE_FPS
    print(f"  -> {label} ({total_frames} frames, {duration_sec:.1f}s)")
    for _ in range(total_frames):
        frame_idx += 1
        page.screenshot(path=os.path.join(FRAMES_DIR, f"frame_{frame_idx:05d}.png"))
        time.sleep(interval)

with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=CHROME_EXEC,
        headless=True,
        args=["--disable-web-security", "--no-sandbox"]
    )
    page = browser.new_page(viewport={"width": 1920, "height": 1080})
    page.goto("http://127.0.0.1:8015/")
    time.sleep(2.0)

    # Scene 1: Intro card visible (first 3s), then overview dashboard (rest)
    capture_scene(page, SCENE_DURATIONS[0], "Scene 1: Intro card + dashboard overview")

    # Scene 2: Highlight System 1 Decider 2B panel
    page.evaluate("document.getElementById('card-decider').scrollIntoView({behavior:'smooth', block:'center'})")
    time.sleep(0.3)
    capture_scene(page, SCENE_DURATIONS[1], "Scene 2: Decider 2B panel highlight")

    # Scene 3: Prompt injection attack
    page.evaluate("loadScenario('injection')")
    time.sleep(0.6)
    page.evaluate("runEvaluation()")
    time.sleep(1.2)   # let UI settle after fetch
    capture_scene(page, SCENE_DURATIONS[2], "Scene 3: Injection attack")

    # Scene 4: Reset then verified courier
    page.evaluate("resetSystem()")
    time.sleep(0.6)
    page.evaluate("loadScenario('delivery_verified')")
    time.sleep(0.5)
    page.evaluate("runEvaluation()")
    time.sleep(1.2)
    capture_scene(page, SCENE_DURATIONS[3], "Scene 4: Verified courier")

    # Scene 5: Scroll to architecture strip + audit ledger overview
    page.evaluate("document.getElementById('arch-strip').scrollIntoView({behavior:'smooth', block:'center'})")
    time.sleep(0.5)
    capture_scene(page, SCENE_DURATIONS[4], "Scene 5: Architecture strip + audit ledger")

    browser.close()

total_duration = sum(SCENE_DURATIONS)
print(f"[3/3] Encoding {frame_idx} frames into {RAW_VIDEO}  (total: {total_duration:.1f}s) ...")
subprocess.run([
    "ffmpeg", "-y",
    "-framerate", str(CAPTURE_FPS),
    "-i", os.path.join(FRAMES_DIR, "frame_%05d.png"),
    "-c:v", "libx264",
    "-preset", "slow",
    "-crf", "16",
    "-pix_fmt", "yuv420p",
    "-r", "30",
    RAW_VIDEO
], check=True)

shutil.rmtree(FRAMES_DIR, ignore_errors=True)
print(f"[✓] Raw video ready: {RAW_VIDEO}")
