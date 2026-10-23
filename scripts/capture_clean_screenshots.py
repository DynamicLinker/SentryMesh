import os
import sys
import threading
import time
from playwright.sync_api import sync_playwright

sys.path.insert(0, "/home/chadpenguin/Projects/AMAZON")
import uvicorn
from sentrymesh.mcp.server import app

SCREENSHOTS_DIR = "/home/chadpenguin/Projects/AMAZON/screenshots"
CHROME_EXEC = "/home/chadpenguin/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome"

os.makedirs(SCREENSHOTS_DIR, exist_ok=True)

def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8016, log_level="error")

srv = threading.Thread(target=run_server, daemon=True)
srv.start()
time.sleep(1.5)

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME_EXEC, headless=True)
    page = b.new_page(viewport={"width": 1920, "height": 1080})
    page.goto("http://127.0.0.1:8016/")
    
    # Hide intro card immediately for clean screenshots
    page.evaluate("document.getElementById('intro-card').style.display = 'none'")
    time.sleep(1.0)
    
    # 1. Clean Standby Dashboard
    page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "01_dashboard_overview.png"))
    print("Captured 01_dashboard_overview.png")
    
    # 2. System 1 & 2 Decider Focus
    page.evaluate("loadScenario('delivery_unverified')")
    time.sleep(0.5)
    page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "02_visitor_scenario_panel.png"))
    print("Captured 02_visitor_scenario_panel.png")
    
    # 3. Prompt Injection Defense
    page.evaluate("loadScenario('injection')")
    time.sleep(0.5)
    page.evaluate("runEvaluation()")
    time.sleep(1.5)
    page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "03_prompt_injection_defense.png"))
    print("Captured 03_prompt_injection_defense.png")
    
    # 4. Verified Courier Access Granted
    page.evaluate("resetSystem()")
    time.sleep(0.5)
    page.evaluate("loadScenario('delivery_verified')")
    time.sleep(0.5)
    page.evaluate("runEvaluation()")
    time.sleep(1.5)
    page.screenshot(path=os.path.join(SCREENSHOTS_DIR, "04_verified_courier_unlock.png"))
    print("Captured 04_verified_courier_unlock.png")
    
    b.close()

print("Clean screenshots generated successfully!")
