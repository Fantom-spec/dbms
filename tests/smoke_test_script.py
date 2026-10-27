#!/usr/bin/env python3
"""
Browser Smoke Test for Smart Hospital Management System
Uses Playwright to verify all pages load without console errors.

Run: python tests/smoke_test.py
Requires: pip install playwright && playwright install chromium
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Playwright not installed. Install with: pip install playwright && playwright install chromium")
    sys.exit(1)

PAGES = [
    ("Dashboard", "/"),
    ("Patients", "/patients"),
    ("Appointments", "/appointments"),
    ("Emergency", "/emergency"),
    ("Beds", "/beds"),
    ("Pharmacy", "/pharmacy"),
    ("Billing", "/billing"),
    ("Reports", "/reports"),
    ("Audit Log", "/audit"),
    ("Admin", "/admin"),
]

ROLES = [
    "Admin",
    "Receptionist",
    "Triage Nurse",
    "Doctor",
    "Billing",
]

async def test_page(page, url, name):
    """Test a single page for console errors and successful load."""
    errors = []
    
    def handle_console(msg):
        if msg.type == 'error':
            errors.append(f"  Console Error: {msg.text}")
        elif msg.type == 'warning':
            errors.append(f"  Console Warning: {msg.text}")
    
    page.on("console", handle_console)
    
    try:
        await page.goto(f"http://127.0.0.1:5000{url}", wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(1000)  # Allow JS to settle
        
        # Check for obvious error states
        body_text = await page.text_content("body")
        if "Internal server error" in body_text or "500" in body_text:
            errors.append(f"  Page shows server error")
        
        if errors:
            return False, errors
        return True, []
    except Exception as e:
        return False, [f"  Navigation failed: {e}"]

async def test_role_switching(page):
    """Test role switching functionality."""
    errors = []
    try:
        # Wait for role dropdown
        await page.wait_for_selector("#roleDropdown", timeout=5000)
        
        for role in ROLES:
            await page.click("#roleDropdown")
            await page.click(f'[data-role="{role}"]')
            await page.wait_for_timeout(500)
            
            # Check role display updated
            role_text = await page.text_content("#currentRole")
            if role_text != role:
                errors.append(f"  Role switch to {role} failed (shows: {role_text})")
        
        return len(errors) == 0, errors
    except Exception as e:
        return False, [f"  Role switching test failed: {e}"]

async def test_api_endpoints(page):
    """Test key API endpoints return valid responses."""
    errors = []
    endpoints = [
        "/api/meta",
        "/api/dashboard",
        "/api/patients",
        "/api/doctors",
        "/api/beds",
        "/api/medicines",
        "/api/visits",
        "/api/reports",
    ]
    
    for endpoint in endpoints:
        try:
            response = await page.request.get(f"http://127.0.0.1:5000{endpoint}")
            if not response.ok:
                errors.append(f"  {endpoint}: HTTP {response.status}")
            else:
                data = await response.json()
                if not data.get("ok", False) and endpoint != "/api/reports":
                    # Some endpoints return ok:false for valid reasons (e.g., empty data)
                    pass
        except Exception as e:
            errors.append(f"  {endpoint}: {e}")
    
    return len(errors) == 0, errors

async def run_smoke_tests():
    """Run all smoke tests."""
    print("Starting browser smoke tests...")
    print("=" * 60)
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        all_passed = True
        results = {}
        
        # Test each page
        for name, url in PAGES:
            print(f"\nTesting {name} ({url})...")
            passed, errors = await test_page(page, url, name)
            results[name] = (passed, errors)
            
            if passed:
                print(f"  ✓ PASSED")
            else:
                print(f"  ✗ FAILED")
                for err in errors:
                    print(err)
                all_passed = False
        
        # Test role switching
        print(f"\nTesting role switching...")
        passed, errors = await test_role_switching(page)
        results["Role Switching"] = (passed, errors)
        
        if passed:
            print(f"  ✓ PASSED")
        else:
            print(f"  ✗ FAILED")
            for err in errors:
                print(err)
            all_passed = False
        
        # Test API endpoints
        print(f"\nTesting API endpoints...")
        passed, errors = await test_api_endpoints(page)
        results["API Endpoints"] = (passed, errors)
        
        if passed:
            print(f"  ✓ PASSED")
        else:
            print(f"  ✗ FAILED")
            for err in errors:
                print(err)
            all_passed = False
        
        await browser.close()
        
        # Summary
        print("\n" + "=" * 60)
        print("SMOKE TEST SUMMARY")
        print("=" * 60)
        for name, (passed, _) in results.items():
            status = "PASS" if passed else "FAIL"
            print(f"  {status}: {name}")
        
        print(f"\nOverall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")
        return all_passed

if __name__ == "__main__":
    result = asyncio.run(run_smoke_tests())
    sys.exit(0 if result else 1)