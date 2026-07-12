#!/bin/bash
# Test script to verify TrimP monitor works

echo "══════════════════════════════════════════════════════════════════"
echo "          🧪 TrimP Monitor Test Script"
echo "══════════════════════════════════════════════════════════════════"
echo ""
echo "This script will:"
echo "  1. Run several compressions"
echo "  2. Show you the database entries"
echo "  3. Explain how to use the monitor"
echo ""
echo "══════════════════════════════════════════════════════════════════"
echo ""

echo "Step 1: Running compressions..."
echo "────────────────────────────────────────────────────────────────"

# Test 1: Small text
echo "Test 1: Small text"
echo "This is a small test message" | TrimP compress --mode bash >/dev/null 2>&1
echo "✓ Done"

# Test 2: pip list
echo "Test 2: pip list (larger output)"
pip list 2>/dev/null | TrimP compress --mode bash >/dev/null 2>&1
echo "✓ Done"

# Test 3: git log
echo "Test 3: git log"
git log --oneline 2>/dev/null | head -20 | TrimP compress --mode bash >/dev/null 2>&1 || echo "✓ Done (or no git repo)"

# Test 4: Directory listing
echo "Test 4: Directory listing"
ls -la | TrimP compress --mode bash >/dev/null 2>&1
echo "✓ Done"

echo ""
echo "Step 2: Checking database..."
echo "────────────────────────────────────────────────────────────────"

sqlite3 ~/.trimp/TrimP.db << 'SQL'
.mode column
.headers on
SELECT 
  SUBSTR(compressed_at, 12, 8) as time,
  compressor,
  tokens_before as before,
  tokens_after as after,
  tokens_before - tokens_after as saved,
  ROUND(CAST(tokens_before - tokens_after AS FLOAT) / tokens_before * 100, 1) || '%' as reduction
FROM compressions 
ORDER BY compressed_at DESC 
LIMIT 10;
SQL

echo ""
echo "══════════════════════════════════════════════════════════════════"
echo "          ✅ RESULTS"
echo "══════════════════════════════════════════════════════════════════"
echo ""

TOTAL=$(sqlite3 ~/.trimp/TrimP.db "SELECT COUNT(*) FROM compressions;")
SAVED=$(sqlite3 ~/.trimp/TrimP.db "SELECT SUM(tokens_before - tokens_after) FROM compressions;")

echo "Total compressions logged: $TOTAL"
echo "Total tokens saved: $SAVED"
echo ""

echo "══════════════════════════════════════════════════════════════════"
echo "          📊 HOW TO USE THE MONITOR"
echo "══════════════════════════════════════════════════════════════════"
echo ""
echo "Option 1: Real-Time Monitor (Recommended)"
echo "────────────────────────────────────────────────────────────────"
echo "  Terminal 1:"
echo "    TrimP monitor"
echo ""
echo "  Terminal 2:"
echo "    pip list | TrimP compress --mode bash"
echo "    git log | TrimP compress --mode bash"
echo ""
echo "  → Watch Terminal 1 update in real-time!"
echo ""
echo ""
echo "Option 2: Dashboard (Web UI)"
echo "────────────────────────────────────────────────────────────────"
echo "  Open: http://localhost:7432"
echo "  → Click 'Optimize' tab to see compression stats"
echo "  → Auto-refreshes every 10 seconds"
echo ""
echo ""
echo "Option 3: Check Database Manually"
echo "────────────────────────────────────────────────────────────────"
echo "  sqlite3 ~/.trimp/TrimP.db \\"
echo "    \"SELECT * FROM compressions ORDER BY compressed_at DESC LIMIT 10;\""
echo ""
echo ""
echo "══════════════════════════════════════════════════════════════════"
echo "          🎯 TRY IT NOW"
echo "══════════════════════════════════════════════════════════════════"
echo ""
echo "Open a new terminal and run:"
echo ""
echo "  TrimP monitor"
echo ""
echo "Then in this terminal, run:"
echo ""
echo "  pip list | TrimP compress --mode bash"
echo ""
echo "Watch the monitor update!"
echo ""
echo "══════════════════════════════════════════════════════════════════"
