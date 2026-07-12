#!/bin/bash
# Quick setup for automatic GitHub Copilot compression

set -e

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "   🚀 TrimP Auto-Interception Setup"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "This will configure TrimP to automatically compress ALL your"
echo "GitHub Copilot chats from ALL repos."
echo ""

# Detect shell
if [ -n "$ZSH_VERSION" ]; then
    SHELL_RC="$HOME/.zshrc"
    SHELL_NAME="zsh"
elif [ -n "$BASH_VERSION" ]; then
    SHELL_RC="$HOME/.bashrc"
    SHELL_NAME="bash"
else
    SHELL_RC="$HOME/.bashrc"
    SHELL_NAME="bash"
fi

echo "📝 Detected shell: $SHELL_NAME"
echo "📝 Config file: $SHELL_RC"
echo ""

# Create .trimp directory if needed
mkdir -p ~/.trimp

# Check if proxy is already running
if lsof -i :8765 > /dev/null 2>&1; then
    echo "⚠️  Port 8765 is already in use. Proxy may already be running."
    echo "   To check: ps aux | grep 'TrimP proxy'"
    echo ""
else
    # Start proxy in background
    echo "🔄 Starting TrimP proxy..."
    nohup TrimP proxy start --upstream github-copilot --port 8765 > ~/.trimp/proxy.log 2>&1 &
    PROXY_PID=$!
    sleep 2
    
    # Verify it started
    if lsof -i :8765 > /dev/null 2>&1; then
        echo "✅ Proxy started successfully (PID: $PROXY_PID)"
    else
        echo "❌ Failed to start proxy. Check ~/.trimp/proxy.log"
        exit 1
    fi
fi

echo ""
echo "🔧 Adding environment variables to $SHELL_RC..."

# Check if already configured
if grep -q "TrimP proxy" "$SHELL_RC" 2>/dev/null; then
    echo "⚠️  Environment variables already exist in $SHELL_RC"
    echo "   Skipping to avoid duplicates."
else
    # Add configuration
    cat >> "$SHELL_RC" <<'ENVVARS'

# ═══════════════════════════════════════════════════════════════
# TrimP - Automatic GitHub Copilot Compression
# Compresses all Copilot chats automatically (60-70% savings)
# ═══════════════════════════════════════════════════════════════
export ANTHROPIC_BASE_URL="http://localhost:8765"
export GITHUB_COPILOT_PROXY="http://localhost:8765"

# Uncomment if using Claude API directly:
# export ANTHROPIC_API_PROXY="http://localhost:8765"
ENVVARS

    echo "✅ Environment variables added"
fi

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "   ✅ Setup Complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "What happens now:"
echo "  1. TrimP proxy is running in background (port 8765)"
echo "  2. Environment variables are configured"
echo "  3. GitHub Copilot will use the proxy automatically"
echo ""
echo "Next steps:"
echo "  1. Open a NEW terminal (to load environment variables)"
echo "  2. Run: TrimP monitor"
echo "  3. Chat with GitHub Copilot in ANY repo"
echo "  4. Watch compressions appear! (60-70% savings)"
echo ""
echo "Useful commands:"
echo "  • Check proxy: lsof -i :8765"
echo "  • View logs:   tail -f ~/.trimp/proxy.log"
echo "  • Monitor:     TrimP monitor"
echo "  • Dashboard:   TrimP dashboard --mode web"
echo ""
echo "To apply changes in THIS terminal:"
echo "  source $SHELL_RC"
echo ""
echo "═══════════════════════════════════════════════════════════════"
