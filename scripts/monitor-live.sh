#!/bin/bash
# Real-time compression monitor for TrimP
# Shows live updates as compressions happen

DB=~/.trimp/TrimP.db

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║           TrimP — Real-Time Compression Monitor               ║"
echo "║      Press Ctrl+C to stop. Updates every 2 seconds.          ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

while true; do
    clear
    echo "═══════════════════════════════════════════════════════════════"
    echo "  TrimP Real-Time Compression Monitor"
    echo "  $(date '+%Y-%m-%d %H:%M:%S')"
    echo "═══════════════════════════════════════════════════════════════"
    echo ""
    
    # Summary stats
    echo "📊 SUMMARY (All Time)"
    echo "───────────────────────────────────────────────────────────────"
    sqlite3 "$DB" "
    SELECT 
      COUNT(*) || ' compressions' as total,
      ROUND(SUM(tokens_before - tokens_after)) || ' tokens saved' as saved,
      ROUND(100.0 * (1 - AVG(CAST(tokens_after AS REAL) / tokens_before)), 1) || '%' as avg_savings
    FROM compressions
    WHERE source = 'hook'
    " 2>/dev/null || echo "No compressions yet"
    echo ""
    
    # By category
    echo "📁 BY CATEGORY"
    echo "───────────────────────────────────────────────────────────────"
    sqlite3 "$DB" "
    SELECT 
      CASE 
        WHEN compressor LIKE '%UserMessage%' THEN '💬 User Messages'
        WHEN compressor = 'BashCompressor' THEN '⚙️  Bash Outputs'
        WHEN compressor LIKE '%Code%' THEN '📄 File Reads'
        ELSE '📦 Other'
      END as category,
      COUNT(*) || ' events' as count,
      ROUND(100.0 * (1 - AVG(CAST(tokens_after AS REAL) / tokens_before)), 1) || '% saved' as savings
    FROM compressions
    WHERE source = 'hook'
    GROUP BY 
      CASE 
        WHEN compressor LIKE '%UserMessage%' THEN '💬 User Messages'
        WHEN compressor = 'BashCompressor' THEN '⚙️  Bash Outputs'
        WHEN compressor LIKE '%Code%' THEN '📄 File Reads'
        ELSE '📦 Other'
      END
    " 2>/dev/null || echo "No data"
    echo ""
    
    # Recent compressions
    echo "🕐 RECENT COMPRESSIONS (Last 5)"
    echo "───────────────────────────────────────────────────────────────"
    sqlite3 "$DB" "
    SELECT 
      substr(datetime(compressed_at, 'localtime'), 12, 8) as time,
      substr(compressor, 1, 25) as algorithm,
      tokens_before || '→' || tokens_after as 'tokens',
      ROUND(100.0 * (tokens_before - tokens_after) / tokens_before, 1) || '%' as saved
    FROM compressions
    WHERE source = 'hook'
    ORDER BY compressed_at DESC 
    LIMIT 5
    " -column -header 2>/dev/null || echo "No compressions yet"
    echo ""
    
    echo "═══════════════════════════════════════════════════════════════"
    echo "  Dashboard: http://localhost:7432"
    echo "  Database: ~/.trimp/TrimP.db"
    echo "  Refreshing in 2s... (Ctrl+C to stop)"
    echo "═══════════════════════════════════════════════════════════════"
    
    sleep 2
done
