# TrimP IntelliJ/PyCharm Integration for GitHub Copilot Chat

This integration enables **real-time token compression** for GitHub Copilot Chat in IntelliJ IDEA, PyCharm, WebStorm, and other JetBrains IDEs.

## How It Works

```
PyCharm/IntelliJ (Copilot Chat)
         │
         ▼ HTTP/HTTPS requests
    ┌────────────────────────┐
    │   TrimP Proxy          │
    │   (localhost:8765)     │
    │  - Compresses context  │
    │  - Logs metrics        │
    └────────────────────────┘
         │
         ▼ Compressed requests
    ┌────────────────────────┐
    │  GitHub Copilot API    │
    │  (api.githubcopilot.com)│
    └────────────────────────┘
```

The proxy intercepts all Copilot Chat requests, compresses the context using TrimP's 15 algorithms, forwards to GitHub, and returns responses - all while logging savings to the TrimP dashboard.

## Quick Start

### 1. Start the Proxy

```bash
cd /Users/nabiharaza/Projects/copilot-token-optimizer
./TrimP-intellij/TrimP-intellij-proxy --port 8765
```

You'll see:
```
🔧 TrimP IntelliJ/PyCharm Proxy for GitHub Copilot Chat

Starting TrimP proxy...
  Port: 8765
  Host: 127.0.0.1
  Integration ID: intellij-chat

Configure PyCharm/IntelliJ:
  Settings -> HTTP Proxy -> Manual: HTTP, Host: localhost, Port: 8765

Dashboard: http://localhost:7432 (run 'TrimP dashboard' separately)
```

### 2. Configure PyCharm/IntelliJ

**Option A: IDE HTTP Proxy Settings (Recommended)**

1. Open **Settings** (⌘, on macOS / Ctrl+Alt+S on Linux/Windows)
2. Navigate to **Appearance & Behavior → System Settings → HTTP Proxy**
3. Select **Manual proxy configuration**
4. Set:
   - **HTTP**: **Host: `localhost` **Port: `8765` **✅ Check "Use this proxy server for all protocols" 5. Click **Apply** → **OK** 6. **Restart PyCharm/IntelliJ**  **Option B: Environment Variables**  ```bash export HTTP_PROXY=http://localhost:8765 export HTTPS_PROXY=http://localhost:8765 # Then launch PyCharm from the same terminal pycharm  ```  ### 3. Use Copilot Chat Normally 
 
 Open Copilot Chat (⌃⌘C / Ctrl+Alt+C) and chat as usual. All context is now automatically compressed!  ### 4. View Savings  ```bash # Real-time monitor TrimP monitor 
 
 # Dashboard (in another terminal) TrimP dashboard 
 
 # Quick stats TrimP quick 
 
 # Detailed savings report TrimP savings 
 ``` 
 
 ## Configuration 
 
 ### Environment Variables 
 
 | Variable | Description | Default | 
 |----------|-------------|---------|
 | `GITHUB_COPILOT_TOKEN` | Your GitHub Copilot API token | Auto-detected from `gh auth token` |
 | `GH_TOKEN` | GitHub CLI token (fallback) | - |
 | `COPILOT_INTEGRATION_ID` | Copilot integration identifier | `intellij-chat` |
 | `TRIMP_COMPRESSION_LEVEL` | Compression aggressiveness (1-5) | `3` |
 | `TRIMP_LOG_LEVEL` | Log level (DEBUG, INFO, WARNING) | `INFO` |
 
 ### Get Your GitHub Copilot Token 
 
 The proxy needs a GitHub token with Copilot access. Options: 
 
 **Option 1: GitHub CLI (easiest)** ```bash gh auth login # Follow prompts gh auth token # Copy this token export GITHUB_COPILOT_TOKEN=$(gh auth token)  ``` 
 
 **Option 2: Personal Access Token**
 
 1. Go to https://github.com/settings/tokens 
 2. Generate new token (classic) with `copilot` scope 
 3. `export GITHUB_COPILOT_TOKEN=your_token_here` 
 
 ## Compression Algorithms Used 
 
 The proxy applies these compressions automatically: 
 
 | Algorithm | Target | Typical Savings | 
 |-----------|--------|-----------------| 
 | **ConversationCompressor** | Chat history | 55-70% | 
 | **BashCompressor** | Terminal output | 60-80% | 
 | **SearchCompressor** | Search/grep results | 70-85% | 
 | **JsonTableCompressor** | JSON/API responses | 60-90% | 
 | **CodeContextTrimmer** | Code files | 40-75% | 
 | **LLMLinguaLite** | General text | 30-60% | 
 | **SemanticChunker** | Long documents | 50-85% | 
 | **UniversalOptimizer** | Auto-detect | Varies | 
 
 **Total typical savings: 55-65%** 
 
 ## Troubleshooting 
 
 ### Proxy not working? 
 
 1. **Verify proxy is running:** 
 ```bash curl http://localhost:8765/health  # Should return {"status":"ok"} 
 ``` 
 
 2. **Check PyCharm is using proxy:** 
 ```bash # In PyCharm terminal echo $HTTP_PROXY # Should be http://localhost:8765 
 ``` 
 
 3. **Restart PyCharm completely** (not just reload) 
 
 4. **Check proxy logs** - they show every compressed request 
 
 ### "Connection refused" or proxy errors 
 
 - Make sure port 8765 is free: `lsof -i :8765` 
 - Try different port: `./TrimP-intellij-proxy --port 8766` 
 - Update PyCharm proxy settings to match 
 
 ### Copilot Chat not loading 
 
 - Check token: `echo $GITHUB_COPILOT_TOKEN` 
 - Verify token works: `curl -H "Authorization: Bearer $GITHUB_COPILOT_TOKEN" https://api.githubcopilot.com/v1/models` 
 - Check proxy logs for auth errors 
 
 ### No compression showing in dashboard 
 
 - Ensure TrimP DB is initialized: `TrimP init` 
 - Check session: `TrimP session show` 
 - Proxy logs show compression stats per request 
 
 ## Advanced Usage 
 
 ### Run with Custom Compression Level 
 
 ```bash export TRIMP_COMPRESSION_LEVEL=5 # Maximum compression ./TrimP-intellij-proxy --port 8765 
 ``` 
 
 ### Run Dashboard Simultaneously 
 
 ```bash # Terminal 1: Proxy ./TrimP-intellij-proxy --port 8765 
 
 # Terminal 2: Dashboard TrimP dashboard --mode web --port 7432 
 
 # Terminal 3: Monitor TrimP monitor 
 ``` 
 
 ### Multiple IDEs 
 
 Run separate proxies on different ports for different IDEs: 
 
 ```bash # PyCharm ./TrimP-intellij-proxy --port 8765 --integration-id pycharm-chat 
 
 # IntelliJ IDEA ./TrimP-intellij-proxy --port 8766 --integration-id intellij-chat 
 
 # WebStorm ./TrimP-intellij-proxy --port 8767 --integration-id webstorm-chat 
 ``` 
 
 ## Architecture 
 
 ``` 
 TrimP-intellij-proxy.py 
 ├── FastAPI server (localhost:8765) 
 │ ├── /v1/chat/completions  → Compress → Forward to api.githubcopilot.com 
 │ ├── /v1/models            → Pass through 
 │ ├── /health               → Health check 
 │ └── /TrimP/stats          → Proxy statistics 
 ├── ChatPayloadOptimizer    → Optimizes entire request body 
 ├── Compressors (15 algos)  → Bash, Search, JSON, Code, Conversation, etc. 
 ├── TrimP Database          → Logs all compression events 
 └── Dashboard Integration   → Real-time metrics at :7432 
 ``` 
 
 ## Files 
 
 ``` TrimP-intellij/ 
 ├── TrimP_intellij_proxy.py  # Main proxy server 
 ├── TrimP-intellij-proxy     # Launch script (executable) 
 └── README.md                # This file 
 ``` 
 
 ## Integration with TrimP CLI 
 
 All proxy compressions are logged to the shared TrimP database, visible in: 
 
 - `TrimP dashboard` - Web dashboard at http://localhost:7432 
 - `TrimP monitor` - Terminal real-time monitor 
 - `TrimP quick` - Quick health check 
 - `TrimP savings` - Dollar savings report 
 - `TrimP stats --by-compressor` - Per-algorithm breakdown 
 
 ## License 
 
 MIT - Part of TrimP (Copilot Token Optimizer) 
 
 --- 
 
 **Built for JetBrains IDEs using GitHub Copilot Chat** 
 
 *Compress your context, save your tokens, ship faster!* 🚀