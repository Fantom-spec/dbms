#!/bin/bash
# Smoke checks for public login, auth enforcement, and removed UI routes.
set -u
BASE_URL="${BASE_URL:-http://127.0.0.1:5000}"
passed=0; failed=0
check() {
  name="$1"; expected="$2"; url="$3"
  code=$(curl -s -o /tmp/hospital-smoke-body -w '%{http_code}' "$url" || true)
  if [ "$code" = "$expected" ]; then echo "PASS $name (HTTP $code)"; passed=$((passed+1));
  else echo "FAIL $name (HTTP $code, expected $expected)"; failed=$((failed+1)); fi
}
echo "Smoke testing $BASE_URL"
check "Login page" 200 "$BASE_URL/login"
check "Protected dashboard redirects" 302 "$BASE_URL/"
check "Unauthenticated API denied" 401 "$BASE_URL/api/meta"
check "Removed schema page" 404 "$BASE_URL/schema"
check "Removed demo page" 404 "$BASE_URL/demo"
check "Removed schema API" 404 "$BASE_URL/api/schema/overview"
check "Removed interactive demo API" 404 "$BASE_URL/api/demo/steps"
echo "Results: $passed passed, $failed failed"
[ "$failed" -eq 0 ]
