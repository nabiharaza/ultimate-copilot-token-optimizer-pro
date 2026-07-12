#!/bin/bash
# TrimP quick install script
# Usage: curl -fsSL <url>/install.sh | bash

set -e

echo "🔧 Installing TrimP — Copilot Token Optimizer..."

# Install Python package
pip install -e "$(dirname "$0")" --quiet

# Initialize data directory + DB
TrimP init

# Run doctor
echo ""
TrimP doctor

echo ""
echo "✅ TrimP installed! Run:"
echo "   TrimP quick              — health check"
echo "   TrimP token-optimizer    — full audit"
echo "   TrimP dashboard          — terminal TUI"
echo "   TrimP dashboard --mode web  — web dashboard at http://localhost:7432"
echo ""
echo "Add to shell profile to auto-init each session:"
echo "   echo 'TrimP session new &>/dev/null' >> ~/.zshrc"
