#!/bin/bash
# Quick verification that TrimP is working across all chat sessions

DB=~/.trimp/TrimP.db

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║              TrimP Compression Verification                   ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

echo "✅ Step 1: Checking database..."
if [ -f "$DB" ]; then
    echo "   ✓ Database exists at $DB"
    table_count=$(sqlite3 "$DB" ".tables" 2>/dev/null | wc -w | tr -d ' ')
    echo "   ✓ $table_count tables created"
else
    echo "   ⚠ Database not yet created at $DB"
    echo "   Run: TrimP proxy start   (then send a message in PyCharm/VS Code)"
    exit 1
fi
echo ""

echo "✅ Step 2: Checking sessions..."
session_count=$(sqlite3 "$DB" "SELECT COUNT(*) FROM sessions" 2>/dev/null || echo "0")
active_count=$(sqlite3 "$DB" "SELECT COUNT(*) FROM sessions WHERE status='active'" 2>/dev/null || echo "0")
echo "   ✓ $session_count total sessions ($active_count active)"
if [ "$session_count" -gt 0 ]; then
    echo ""
    echo "   Recent sessions (date/time, model, tokens saved):"
    sqlite3 "$DB" "
    SELECT '   • ' || datetime(started_at, 'localtime') ||
           ' | model: ' || COALESCE(model,'unknown') ||
           ' | saved: ' || tokens_saved || ' tokens' ||
           ' | status: ' || status
    FROM sessions
    ORDER BY started_at DESC
    LIMIT 5
    " 2>/dev/null
fi
echo ""

echo "✅ Step 3: Checking compressions..."
comp_count=$(sqlite3 "$DB" "SELECT COUNT(*) FROM compressions" 2>/dev/null || echo "0")
if [ "$comp_count" -gt 0 ]; then
    echo "   ✓ $comp_count compressions logged"
    echo ""
    echo "   Recent compressions:"
    sqlite3 "$DB" "
    SELECT
      '   • ' || datetime(compressed_at, 'localtime') || '  ' ||
      printf('%-26s', compressor) || '  ' ||
      tokens_before || '→' || tokens_after || '  ' ||
      ROUND(100.0*(tokens_before-tokens_after)/MAX(tokens_before,1),1) || '% saved'
    FROM compressions
    ORDER BY compressed_at DESC
    LIMIT 5
    " 2>/dev/null
else
    echo "   ⚠ No compressions yet"
    echo ""
    echo "   To start tracking:"
    echo "   1. Start proxy:   TrimP proxy start --upstream github-copilot"
    echo "   2. Set env var:   export OPENAI_BASE_URL=http://localhost:8765"
    echo "   3. Chat in PyCharm — each message sent will be tracked here"
fi
echo ""

echo "✅ Step 4: Dashboard status..."
if curl -s -o /dev/null -w "%{http_code}" http://localhost:7432/api/health 2>/dev/null | grep -q "200"; then
    echo "   ✓ Dashboard running at http://localhost:7432"
    db_compressions=$(curl -s http://localhost:7432/api/health 2>/dev/null | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['db']['compressions'])" 2>/dev/null || echo "?")
    echo "   ✓ Dashboard DB reports: $db_compressions compressions"
else
    echo "   ⚠ Dashboard not running. Start with: TrimP dashboard"
fi
echo ""

echo "✅ Step 5: Proxy status..."
if curl -s -o /dev/null -w "%{http_code}" http://localhost:8765/TrimP/status 2>/dev/null | grep -q "200"; then
    echo "   ✓ Proxy running at http://localhost:8765"
else
    echo "   ⚠ Proxy not running. Start with: TrimP proxy start"
fi
echo ""

echo "═══════════════════════════════════════════════════════════════"
echo " DB:      $DB"
echo " Summary: TrimP is $([ "${comp_count:-0}" -gt 0 ] && echo '✅ ACTIVE and TRACKING' || echo '⏸  READY — awaiting first chat')"
echo "═══════════════════════════════════════════════════════════════"
