import os
import shutil
import subprocess
import sys
import threading
import time
import uvicorn
from playwright.sync_api import sync_playwright

CHROME_EXEC = "/home/chadpenguin/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome"
TEMP_VIDEO_DIR = "/home/chadpenguin/Projects/AMAZON/temp_video_record"
OUTPUT_VIDEO = "/home/chadpenguin/Projects/AMAZON/raw_demo_video.mp4"

os.makedirs(TEMP_VIDEO_DIR, exist_ok=True)

# 1. Start in-process uvicorn server in a daemon thread
def start_server():
    from sentrymesh.mcp.server import app
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="warning")

server_thread = threading.Thread(target=start_server, daemon=True)
server_thread.start()
print("[1/5] In-process FastAPI server started on http://127.0.0.1:8000...")
time.sleep(2.0)

print("[2/5] Launching Playwright Chromium with video recording...")
with sync_playwright() as p:
    browser = p.chromium.launch(
        executable_path=CHROME_EXEC,
        headless=True,
        args=["--no-sandbox", "--disable-gpu", "--window-size=1280,720"],
    )
    context = browser.new_context(
        record_video_dir=TEMP_VIDEO_DIR,
        record_video_size={"width": 1280, "height": 720},
        viewport={"width": 1280, "height": 720},
    )
    page = context.new_page()

    print("[2/4] Navigating to SentryMesh dashboard...")
    page.goto("http://127.0.0.1:8000/", wait_until="networkidle")
    time.sleep(4.0)

    # 1. Show dashboard metrics
    print("  -> Scene 1: Dashboard overview")
    time.sleep(12.0)

    # 2. Trigger Prompt Injection Attack Scenario
    print("  -> Scene 2: Testing prompt injection attack")
    page.click("button:has-text('Prompt Injection Attack')")
    time.sleep(2.0)
    page.click("#btn-trigger")
    time.sleep(14.0)

    # 3. Reset Hardware State
    print("  -> Scene 3: Resetting hardware state")
    page.click("button:has-text('Reset Hardware State')")
    time.sleep(3.0)

    # 4. Trigger Scheduled Amazon Courier Scenario
    print("  -> Scene 4: Testing scheduled Amazon courier")
    page.click("button:has-text('Amazon Scheduled Courier')")
    time.sleep(2.0)
    page.click("#btn-trigger")
    time.sleep(14.0)

    # 5. Final overview of benchmark metrics and audit ledger
    print("  -> Scene 5: Benchmark overview and audit trail")
    time.sleep(15.0)

    print("[3/4] Closing browser context to flush video...")
    page.close()
    context.close()
    browser.close()

# Find the generated video file
recorded_files = [f for f in os.listdir(TEMP_VIDEO_DIR) if f.endswith(".webm")]
if not recorded_files:
    raise RuntimeError("No recorded video file found in temporary directory.")

raw_webm = os.path.join(TEMP_VIDEO_DIR, recorded_files[0])
print(f"[4/4] Transcoding {raw_webm} to MP4...")

ffmpeg_cmd = [
    "ffmpeg", "-y",
    "-i", raw_webm,
    "-c:v", "libx264",
    "-preset", "fast",
    "-crf", "18",
    "-pix_fmt", "yuv420p",
    "-r", "30",
    OUTPUT_VIDEO
]
subprocess.run(ffmpeg_cmd, check=True)
shutil.rmtree(TEMP_VIDEO_DIR, ignore_errors=True)
print(f"[✓] Raw video created: {OUTPUT_VIDEO}")
