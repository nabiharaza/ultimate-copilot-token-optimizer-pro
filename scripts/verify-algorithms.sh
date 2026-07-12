#!/bin/bash
# Comprehensive algorithm verification for teams

set -e

echo "🔬 TrimP Algorithm Verification Suite"
echo "======================================"
echo ""

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

test_compression() {
    local name="$1"
    local input="$2"
    local mode="$3"
    local expected_min_savings="$4"
    
    echo -n "Testing $name... "
    
    # Run compression
    output=$(echo "$input" | TrimP compress --mode "$mode" 2>&1)
    
    # Extract savings
    savings=$(echo "$output" | grep "Tokens saved:" | sed 's/.*~//' | tr -d ',')
    
    # Check if we got savings
    if [ -n "$savings" ] && [ "$savings" -ge "$expected_min_savings" ]; then
        echo -e "${GREEN}✓ PASS${NC} (saved $savings tokens)"
        PASSED=$((PASSED + 1))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC} (saved $savings tokens, expected >=$expected_min_savings)"
        FAILED=$((FAILED + 1))
        return 1
    fi
}

echo "📦 1. Testing Bash/Command Output Compression"
echo "───────────────────────────────────────────"
test_compression "pytest output" "$(cat <<EOF
test_user.py::test_login PASSED [25%]
test_user.py::test_logout PASSED [50%]
test_user.py::test_register PASSED [75%]
test_user.py::test_delete PASSED [100%]
======================== 4 passed in 0.05s ========================
EOF
)" "bash" 20

test_compression "npm install" "$(cat <<EOF
npm WARN deprecated package@1.0.0: This package is deprecated
added 247 packages, and audited 248 packages in 5s
42 packages are looking for funding
found 0 vulnerabilities
EOF
)" "bash" 10

test_compression "git log" "$(cat <<EOF
commit 3a4f2b1c5d6e7f8g9h0i1j2k3l4m5n6o7p8q
Author: Developer <dev@example.com>
Date:   Fri Jun 29 10:00:00 2026

    Fix authentication bug in login endpoint
    
    - Added password validation
    - Fixed session handling
    - Updated tests

commit 9z8y7x6w5v4u3t2s1r0q9p8o7n6m5l4k3j2i
Author: Developer <dev@example.com>
Date:   Thu Jun 28 15:30:00 2026

    Implement user registration API
EOF
)" "bash" 30

echo ""
echo "🔍 2. Testing Search/Grep Output Compression"
echo "───────────────────────────────────────────"

# Generate 50 search results
search_output=""
for i in {1..50}; do
    search_output+="src/app/user/model_$i.py:25: def authenticate_user(username: str, password: str)
"
done

test_compression "grep results" "$search_output" "search" 200

echo ""
echo "📊 3. Testing JSON/Tabular Compression"
echo "───────────────────────────────────────────"
test_compression "JSON array" '[
  {"name": "Alice", "age": 30, "city": "NYC"},
  {"name": "Bob", "age": 25, "city": "SF"},
  {"name": "Charlie", "age": 35, "city": "LA"},
  {"name": "David", "age": 28, "city": "Chicago"},
  {"name": "Eve", "age": 32, "city": "Boston"}
]' "json" 20

echo ""
echo "🔧 4. Testing Real-World Scenarios"
echo "───────────────────────────────────────────"

# Test with actual pip list
if command -v pip &> /dev/null; then
    test_compression "pip list (real)" "$(pip list 2>&1 | head -30)" "bash" 50
fi

# Test with git status
if git rev-parse --git-dir > /dev/null 2>&1; then
    test_compression "git status (real)" "$(git status 2>&1)" "bash" 10
fi

echo ""
echo "🧪 5. Testing Algorithm Selection"
echo "───────────────────────────────────────────"

# Large output that should trigger algorithm compression
large_output=""
for i in {1..100}; do
    large_output+="Line $i: This is a test line with some content that should compress well.
"
done

test_compression "Large output (triggers zstd/brotli)" "$large_output" "bash" 500

echo ""
echo "🔒 6. Testing Security (Credential Redaction)"
echo "───────────────────────────────────────────"

sensitive_input="export DATABASE_PASSWORD=SuperSecret123
export API_KEY=sk-1234567890abcdef
export BEARER_TOKEN=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"

output=$(echo "$sensitive_input" | TrimP compress --mode bash 2>&1)

if echo "$output" | grep -q "<redacted>"; then
    echo -e "${GREEN}✓ PASS${NC} Credentials redacted"
    PASSED=$((PASSED + 1))
else
    echo -e "${RED}✗ FAIL${NC} Credentials not redacted"
    FAILED=$((FAILED + 1))
fi

if ! echo "$output" | grep -qE "(SuperSecret|sk-1234|eyJhbG)"; then
    echo -e "${GREEN}✓ PASS${NC} No secrets leaked"
    PASSED=$((PASSED + 1))
else
    echo -e "${RED}✗ FAIL${NC} Secrets leaked!"
    FAILED=$((FAILED + 1))
fi

echo ""
echo "📈 7. Testing Database Logging"
echo "───────────────────────────────────────────"

before_count=$(sqlite3 ~/.trimp/TrimP.db "SELECT COUNT(*) FROM compressions")
echo "test" | TrimP compress --mode bash > /dev/null 2>&1
after_count=$(sqlite3 ~/.trimp/TrimP.db "SELECT COUNT(*) FROM compressions")

if [ "$after_count" -gt "$before_count" ]; then
    echo -e "${GREEN}✓ PASS${NC} Compression logged to database"
    PASSED=$((PASSED + 1))
else
    echo -e "${RED}✗ FAIL${NC} Database logging failed"
    FAILED=$((FAILED + 1))
fi

echo ""
echo "💾 8. Testing Installed Algorithms"
echo "───────────────────────────────────────────"

python3 << 'PYEOF'
import sys

# Test zstandard
try:
    import zstandard
    print("✓ zstandard:", zstandard.__version__)
    sys.exit(0)
except ImportError:
    print("✗ zstandard: NOT INSTALLED")
    sys.exit(1)
PYEOF
[ $? -eq 0 ] && PASSED=$((PASSED + 1)) || FAILED=$((FAILED + 1))

python3 << 'PYEOF'
import sys

# Test brotli
try:
    import brotli
    print("✓ brotli: installed")
    sys.exit(0)
except ImportError:
    print("✗ brotli: NOT INSTALLED")
    sys.exit(1)
PYEOF
[ $? -eq 0 ] && PASSED=$((PASSED + 1)) || FAILED=$((FAILED + 1))

echo ""
echo "📊 9. Compression Statistics"
echo "───────────────────────────────────────────"

sqlite3 ~/.trimp/TrimP.db << 'SQL'
SELECT 
    compressor,
    COUNT(*) as compressions,
    SUM(tokens_before) as total_before,
    SUM(tokens_after) as total_after,
    ROUND(100.0 * (SUM(tokens_before) - SUM(tokens_after)) / SUM(tokens_before), 1) || '%' as avg_savings
FROM compressions
GROUP BY compressor
ORDER BY total_before DESC;
SQL

echo ""
echo "======================================"
echo "📊 Final Results"
echo "======================================"
echo -e "Passed: ${GREEN}$PASSED${NC}"
echo -e "Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}🎉 All tests passed! TrimP is production-ready.${NC}"
    exit 0
else
    echo -e "${YELLOW}⚠️  Some tests failed. Review output above.${NC}"
    exit 1
fi
