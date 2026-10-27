#!/bin/bash
# Quick Smoke Test - validates API endpoints and page loads without browser
# Run: bash tests/smoke_test.sh

set -e

BASE_URL="http://127.0.0.1:5000"
API_BASE="${BASE_URL}/api"

echo "=== Smart Hospital Management System - Quick Smoke Test ==="
echo "Testing against: $BASE_URL"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

passed=0
failed=0

test_endpoint() {
    local name=$1
    local url=$2
    local expected_code=${3:-200}
    
    echo -n "Testing $name... "
    response=$(curl -s -w "\n%{http_code}" -H "X-Role: Admin" -H "X-Requested-With: HospitalApp" "$url" 2>/dev/null || echo -e "\n000")
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | head -n-1)
    
    if [ "$http_code" = "$expected_code" ]; then
        # Check if it's valid JSON envelope
        if echo "$body" | jq -e '.ok != null' >/dev/null 2>&1; then
            ok=$(echo "$body" | jq -r '.ok')
            if [ "$ok" = "true" ] || [ "$ok" = "false" ]; then
                echo -e "${GREEN}PASS${NC} (HTTP $http_code, ok=$ok)"
                ((passed++))
                return 0
            fi
        fi
        echo -e "${YELLOW}WARN${NC} (HTTP $http_code, not envelope format)"
        ((passed++))
        return 0
    else
        echo -e "${RED}FAIL${NC} (HTTP $http_code, expected $expected_code)"
        ((failed++))
        return 1
    fi
}

test_page() {
    local name=$1
    local url=$2
    
    echo -n "Testing $name page... "
    response=$(curl -s -w "\n%{http_code}" "$url" 2>/dev/null || echo -e "\n000")
    http_code=$(echo "$response" | tail -n1)
    
    if [ "$http_code" = "200" ]; then
        echo -e "${GREEN}PASS${NC} (HTTP 200)"
        ((passed++))
        return 0
    else
        echo -e "${RED}FAIL${NC} (HTTP $http_code)"
        ((failed++))
        return 1
    fi
}

# Check if server is running
echo "Checking server availability..."
if ! curl -s "$BASE_URL" >/dev/null 2>&1; then
    echo -e "${RED}Server not running at $BASE_URL${NC}"
    echo "Start with: flask --app app run --debug"
    exit 1
fi
echo -e "${GREEN}Server is running${NC}"
echo ""

# Test pages
echo "=== Page Load Tests ==="
test_page "Dashboard" "$BASE_URL/"
test_page "Patients" "$BASE_URL/patients"
test_page "Appointments" "$BASE_URL/appointments"
test_page "Emergency" "$BASE_URL/emergency"
test_page "Beds" "$BASE_URL/beds"
test_page "Pharmacy" "$BASE_URL/pharmacy"
test_page "Billing" "$BASE_URL/billing"
test_page "Reports" "$BASE_URL/reports"
test_page "Audit Log" "$BASE_URL/audit"
test_page "Guided Demo" "$BASE_URL/demo"
test_page "Schema Explorer" "$BASE_URL/schema"
test_page "Admin" "$BASE_URL/admin"

echo ""
echo "=== API Endpoint Tests ==="
test_endpoint "Meta" "$API_BASE/meta"
test_endpoint "Dashboard Data" "$API_BASE/dashboard"
test_endpoint "Patients List" "$API_BASE/patients"
test_endpoint "Doctors List" "$API_BASE/doctors"
test_endpoint "Beds" "$API_BASE/beds"
test_endpoint "Medicines" "$API_BASE/medicines"
test_endpoint "Visits" "$API_BASE/visits"
test_endpoint "Reports Catalogue" "$API_BASE/reports"
test_endpoint "Schema Overview" "$API_BASE/schema/overview"
test_endpoint "Schema ER Diagram" "$API_BASE/schema/er"
test_endpoint "Audit Log" "$API_BASE/audit"
test_endpoint "Lookups" "$API_BASE/lookups"
test_endpoint "Demo Steps" "$API_BASE/demo/steps"
test_endpoint "Demo State" "$API_BASE/demo/state"

# Test write endpoints (should return 403 without proper CSRF or 400 for validation)
echo ""
echo "=== Write Endpoint Validation (expect 400/403) ==="
echo -n "Testing POST /api/patients (no data)... "
response=$(curl -s -w "\n%{http_code}" -X POST -H "Content-Type: application/json" -H "X-Role: Admin" -H "X-Requested-With: HospitalApp" -d '{}' "$API_BASE/patients" 2>/dev/null || echo -e "\n000")
http_code=$(echo "$response" | tail -n1)
if [ "$http_code" = "400" ] || [ "$http_code" = "403" ]; then
    echo -e "${GREEN}PASS${NC} (correctly rejects empty body with HTTP $http_code)"
    ((passed++))
else
    echo -e "${RED}FAIL${NC} (HTTP $http_code, expected 400/403)"
    ((failed++))
fi

# Summary
echo ""
echo "=== Summary ==="
echo -e "Passed: ${GREEN}$passed${NC}"
echo -e "Failed: ${RED}$failed${NC}"

if [ $failed -eq 0 ]; then
    echo -e "\n${GREEN}All smoke tests passed!${NC}"
    exit 0
else
    echo -e "\n${RED}Some smoke tests failed.${NC}"
    exit 1
fi