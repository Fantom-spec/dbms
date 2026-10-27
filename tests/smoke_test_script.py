#!/usr/bin/env python3
"""Browser smoke tests for the authentication-first application.

Requires: pip install playwright && playwright install chromium
Start the app before running this script.
"""
import asyncio
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Playwright not installed. Install with: pip install playwright && playwright install chromium")
    raise SystemExit(1)
BASE = "http://127.0.0.1:5000"
async def run():
    failures = []
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        errors = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        response = await page.goto(BASE + "/login", wait_until="networkidle", timeout=30000)
        if response is None or response.status != 200:
            failures.append("Login page did not return HTTP 200")
        if not await page.locator("#loginForm").count():
            failures.append("Login form was not rendered")
        for path in ("/", "/patients", "/appointments", "/emergency", "/beds", "/pharmacy", "/billing", "/reports", "/audit", "/admin"):
            response = await page.request.get(BASE + path, max_redirects=0)
            if response.status not in (302, 303):
                failures.append(f"Protected page {path} returned {response.status}, expected redirect to login")
        for path in ("/schema", "/demo", "/api/schema/overview", "/api/demo/steps"):
            response = await page.request.get(BASE + path, max_redirects=0)
            if response.status != 404:
                failures.append(f"Removed endpoint {path} returned {response.status}, expected 404")
        response = await page.request.get(BASE + "/api/meta")
        if response.status != 401:
            failures.append(f"Unauthenticated API returned {response.status}, expected 401")
        if errors:
            failures.extend("Browser JS error: " + error for error in errors)
        await browser.close()
    if failures:
        print("SMOKE TEST FAILED")
        print("\n".join("- " + item for item in failures))
        raise SystemExit(1)
    print("SMOKE TEST PASSED: login page, auth enforcement, and removed routes verified")
if __name__ == "__main__":
    asyncio.run(run())
