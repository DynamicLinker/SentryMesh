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
FRAMES_DIR = "/home/chadpenguin/Projects/AMAZON/video_frames"
RAW_VIDEO = "/home/chadpenguin/Projects/AMAZON/raw_demo_video.mp4"

os.makedirs(FRAMES_DIR, exist_ok=True)

# 1. Start server in daemon thread
def run_srv():
    from sentrymesh.mcp.server import app
    uvicorn.run(app, host="127.0.0.1", port=8005, log_level="error")

srv_thread = threading.Thread(target=run_srv, daemon=True)
srv_thread.start()
print("[1/3] SentryMesh server listening on http://127.0.0.1:8005...")
time.sleep(1.5)

# 2. Capture high-resolution frames with Playwright
print("[2/3] Capturing browser interaction scenes...")
frame_idx = 0

def capture_scene(page, duration_sec, fps=4):
    global frame_idx
    total_frames = int(duration_sec * fps)
    step_sleep = 1.0 / fps
    for _ in range(total_frames):
        frame_idx += 1
        path = os.path.join(FRAMES_DIR, f"frame_{frame_idx:05d}.png")
        page.screenshot(path=path)
        time.sleep(step_sleep)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME_EXEC, headless=True)
    page = b.new_page(viewport={"width": 1280, "height": 720})
    page.goto("http://127.0.0.1:8005/")
    time.sleep(1.5)

    # Scene 1: Introduction & Architecture (0.0s - 16.0s = 16s)
    print("  -> Scene 1: Introduction & Architecture (16s)")
    capture_scene(page, 16.0)

    # Scene 2: Strands Decider 2B Reflex Layer Highlight (16.0s - 32.5s = 16.5s)
    print("  -> Scene 2: Highlighting System 1 Decider 2B Panel (16.5s)")
    page.evaluate("document.getElementById('decider-panel').scrollIntoView({behavior: 'smooth', block: 'center'})")
    capture_scene(page, 16.5)

    # Scene 3: Prompt Injection Attack Demonstration (32.5s - 49.5s = 17s)
    print("  -> Scene 3: Triggering Prompt Injection Attack (17s)")
    page.evaluate("loadScenario('injection')")
    time.sleep(0.5)
    page.evaluate("runEvaluation()")
    capture_scene(page, 17.0)

    # Scene 4: Reset & Scheduled Amazon Courier Demonstration (49.5s - 65.5s = 16s)
    print("  -> Scene 4: Triggering Scheduled Amazon Courier (16s)")
    page.evaluate("resetSystem()")
    time.sleep(0.5)
    page.evaluate("loadScenario('delivery_verified')")
    time.sleep(0.5)
    page.evaluate("runEvaluation()")
    capture_scene(page, 16.0)

    # Scene 5: Benchmark Summary & Final Overview (65.5s - 78.5s = 13s)
    print("  -> Scene 5: Benchmark Overview & Final Ledger (13s)")
    page.evaluate("window.scrollTo({top: 0, behavior: 'smooth'})")
    capture_scene(page, 13.0)

    b.close()

# 3. Assemble frames into MP4 with FFmpeg
print(f"[3/3] Encoding {frame_idx} captured frames into {RAW_VIDEO}...")
ffmpeg_cmd = [
    "ffmpeg", "-y",
    "-framerate", "4",
    "-i", os.path.join(FRAMES_DIR, "frame_%05d.png"),
    "-c:v", "libx264",
    "-preset", "fast",
    "-crf", "18",
    "-pix_fmt", "yuv420p",
    "-r", "30",
    RAW_VIDEO
]
subprocess.run(ffmpeg_cmd, check=True)
shutil.rmtree(FRAMES_DIR, ignore_errors=True)
print(f"[✓] Raw demonstration video created successfully: {RAW_VIDEO}")
