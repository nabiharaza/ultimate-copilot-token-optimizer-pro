#!/bin/bash
# Test all GitHub Copilot models through BYOK proxy

echo "🧪 Testing all GitHub Copilot models..."
echo ""

MODELS=(
  "gpt-4o"
  "claude-sonnet-4.6"
  "claude-sonnet-4.5"
  "gpt-5.4"
  "gpt-5.4-mini"
  "gpt-5.5"
  "claude-opus-4.8"
  "o1"
  "gemini-3.1-pro-preview"
)

PROMPT="What is 3+3? Reply with just the answer."

for model in "${MODELS[@]}"; do
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "Testing: $model"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  
  COPILOT_PROVIDER_BASE_URL=http://localhost:8766/v1 \
  COPILOT_MODEL=$model \
  timeout 15s copilot -p "$PROMPT" --allow-all --silent 2>&1 | head -10
  
  EXIT_CODE=$?
  
  if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ $model - SUCCESS"
  elif [ $EXIT_CODE -eq 124 ]; then
    echo "⏱️  $model - TIMEOUT"
  else
    echo "❌ $model - FAILED"
  fi
  
  echo ""
  sleep 2
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test complete! Check which models worked above."
