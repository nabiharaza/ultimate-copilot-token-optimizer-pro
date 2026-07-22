"""TLS interception bridge for GitHub Copilot Chat in JetBrains IDEs.

The JetBrains Copilot plugin keeps ownership of authentication. This module is
loaded as a mitmproxy addon, rewrites only supported chat JSON payloads, and
posts local trace data to TrimP's dashboard/proxy service.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import selectors
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from TrimP.model_utils import extract_model, normalize_copilot_model

try:  # Available when mitmdump loads this file as an addon.
    from mitmproxy import ctx, http
except ImportError:  # Lifecycle/configuration helpers do not require mitmproxy.
    ctx = None
    http = None


DATA_DIR = Path.home() / ".trimp" / "jetbrains"
MITM_DIR = DATA_DIR / "mitmproxy"
STATE_FILE = DATA_DIR / "state.json"
PID_FILE = DATA_DIR / "proxy.pid"
LOG_FILE = DATA_DIR / "proxy.log"
WORKER_LOG_FILE = DATA_DIR / "optimizer_worker.log"
SPOOL_FILE = DATA_DIR / "trace-spool.jsonl"
CONFIG_STATE_FILE = DATA_DIR / "ide-config.json"
DEFAULT_PORT = 8767
DEFAULT_TRACE_URL = "http://127.0.0.1:8766/v1/TrimP/trace"
CA_CERT = MITM_DIR / "mitmproxy-ca-cert.pem"

COPILOT_HOST_PATTERN = (
    r"(^|\.)githubcopilot\.com(:[0-9]+)?$|"
    r"^copilot-proxy\.githubusercontent\.com(:[0-9]+)?$|"
    r"^(?i:trimp\.local)(:[0-9]+)?$"
)
SESSION_KEYS = (
    "conversation_id",
    "conversationId",
    "session_id",
    "sessionId",
    "thread_id",
    "threadId",
    "prompt_cache_key",
)
PROXY_OPTIONS = {
    "customHttpProxyEnabled": "true",
    "customHttpProxyHost": "127.0.0.1",
    "customHttpProxyPort": str(DEFAULT_PORT),
    "customHttpProxyAuthEnabled": "false",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)


def _update_state(**updates: Any) -> dict[str, Any]:
    state = _read_json(STATE_FILE)
    state.update(updates)
    state["updated_at"] = _now_iso()
    _write_json(STATE_FILE, state)
    return state


def _update_editor_signal(source: str, **updates: Any) -> dict[str, Any]:
    state = _read_json(STATE_FILE)
    signals = state.get("editor_signals")
    if not isinstance(signals, dict):
        signals = {}
    current = signals.get(source)
    if not isinstance(current, dict):
        current = {}
    current.update(updates)
    current["updated_at"] = _now_iso()
    signals[source] = current
    state["editor_signals"] = signals
    state["updated_at"] = _now_iso()
    _write_json(STATE_FILE, state)
    return current


def _content_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("text", "content"):
            if key in value:
                text = _content_text(value[key])
                if text:
                    return text
        return ""
    if isinstance(value, list):
        return "\n".join(filter(None, (_content_text(item) for item in value)))
    return ""


def _extract_user_prompt(body: dict[str, Any]) -> str:
    messages = body.get("messages")
    if isinstance(messages, list):
        for item in reversed(messages):
            if isinstance(item, dict) and item.get("role") == "user":
                text = _content_text(item.get("content"))
                if text.strip():
                    return text.strip()

    value = body.get("input")
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        for item in reversed(value):
            if isinstance(item, dict) and item.get("role") == "user":
                text = _content_text(item.get("content"))
                if text.strip():
                    return text.strip()
    return ""


def _request_source(flow: Any, body: dict[str, Any] | None = None) -> str:
    """Identify the IDE without relying on the shared proxy port."""
    headers = getattr(flow.request, "headers", {})
    values = " ".join(
        str(headers.get(name, ""))
        for name in (
            "user-agent",
            "x-github-copilot-integration-id",
            "x-client-name",
            "x-editor-version",
        )
    ).lower()
    if body:
        values += " " + json.dumps(body, ensure_ascii=False).lower()
    if "vscode" in values or "visual studio code" in values:
        return "vscode-copilot-chat"
    if "rider" in values:
        return "rider-copilot-chat"
    return "pycharm-copilot-chat"


def _is_copilot_host(host: str) -> bool:
    return host.endswith("githubcopilot.com") or host == "copilot-proxy.githubusercontent.com"


def _body_has_chat_payload(body: dict[str, Any]) -> bool:
    if not isinstance(body, dict):
        return False
    if isinstance(body.get("messages"), list) or isinstance(body.get("input"), (str, list)):
        return True
    if isinstance(body.get("model"), str) and any(key in body for key in ("prompt", "suffix", "stream")):
        return True
    for envelope in ("request", "payload", "body"):
        nested = body.get(envelope)
        if isinstance(nested, dict) and _body_has_chat_payload(nested):
            return True
    return False


def _is_supported_copilot_request(host: str, path: str, method: str, body: dict[str, Any]) -> bool:
    if not (_is_copilot_host(host) and method.upper() == "POST"):
        return False
    if "/chat/completions" in path or path.endswith("/responses") or path.endswith("/completions"):
        return True
    return _body_has_chat_payload(body)


def _probe_response(flow: Any) -> None:
    try:
        body = json.loads(flow.request.get_text(strict=False) or "{}")
    except Exception:
        body = {}
    if not isinstance(body, dict):
        body = {}
    request_source = _request_source(flow, body)
    raw_model, model_source = extract_model(body)
    normalized_model = normalize_copilot_model(raw_model, fallback="probe")
    has_payload = _body_has_chat_payload(body)
    signal = _update_editor_signal(
        request_source,
        configured=True,
        probe_ok=True,
        last_probe_at=_now_iso(),
        last_probe_model=normalized_model,
        last_probe_model_source=model_source,
        last_probe_payload_ok=has_payload,
    )
    flow.response = http.Response.make(
        200,
        json.dumps({
            "status": "ok",
            "intercepted": True,
            "request_source": request_source,
            "model": normalized_model,
            "payload_ok": has_payload,
            "signal": signal,
        }),
        {"Content-Type": "application/json"},
    )


def _assistant_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if isinstance(choices, list):
        chunks = []
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message") or choice.get("delta")
            if isinstance(message, dict):
                chunks.append(_content_text(message.get("content")))
        if any(chunks):
            return "".join(chunks).strip()

    output = payload.get("output")
    if isinstance(output, list):
        return "\n".join(
            filter(
                None,
                (
                    _content_text(item.get("content"))
                    for item in output
                    if isinstance(item, dict)
                ),
            )
        ).strip()
    return ""


def _usage(payload: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    if isinstance(payload.get("usage"), dict):
        result["usage"] = payload["usage"]
    if isinstance(payload.get("copilot_usage"), dict):
        result["copilot_usage"] = payload["copilot_usage"]
    return result


def _parse_response(text: str, content_type: str) -> tuple[dict[str, Any], str, dict[str, Any]]:
    stripped = text.lstrip()
    if "json" in content_type.lower() or stripped.startswith("{"):
        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                return payload, _assistant_text(payload), _usage(payload)
        except Exception:
            pass

    events: list[dict[str, Any]] = []
    assistant_chunks: list[str] = []
    actual_usage: dict[str, Any] = {}
    for line in text.splitlines():
        if not line.startswith("data:"):
            continue
        raw = line[5:].strip()
        if not raw or raw == "[DONE]":
            continue
        try:
            event = json.loads(raw)
        except Exception:
            continue
        if not isinstance(event, dict):
            continue
        events.append(event)
        assistant = _assistant_text(event)
        if assistant:
            assistant_chunks.append(assistant)
        if isinstance(event.get("delta"), str) and "output_text" in str(event.get("type", "")):
            assistant_chunks.append(event["delta"])
        event_usage = _usage(event)
        if event_usage:
            actual_usage = event_usage
        response = event.get("response")
        if isinstance(response, dict):
            response_usage = _usage(response)
            if response_usage:
                actual_usage = response_usage

    response_body = {
        "stream": True,
        "event_count": len(events),
        "events": events[-80:],
        "raw": text[:500_000],
        "raw_truncated": len(text) > 500_000,
    }
    return response_body, "".join(assistant_chunks).strip(), actual_usage


def _recursive_value(value: Any, keys: tuple[str, ...], depth: int = 0) -> str:
    if depth > 7:
        return ""
    if isinstance(value, dict):
        for key in keys:
            candidate = value.get(key)
            if isinstance(candidate, (str, int)) and str(candidate).strip():
                return str(candidate).strip()
        for child in value.values():
            candidate = _recursive_value(child, keys, depth + 1)
            if candidate:
                return candidate
    elif isinstance(value, list):
        for child in value:
            candidate = _recursive_value(child, keys, depth + 1)
            if candidate:
                return candidate
    return ""


def _session_id(body: dict[str, Any], prompt: str, namespace: str = "ide") -> str:
    key = _recursive_value(body, SESSION_KEYS)
    if not key:
        seed = prompt or json.dumps(body.get("model", "unknown"))
        key = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:20]
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", key).strip("-")[:120]
    return f"{namespace}-{safe or 'chat'}"


def _git_value(cwd: str, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=cwd, stderr=subprocess.DEVNULL, text=True, timeout=2
        ).strip()
    except Exception:
        return ""


def _path_from_uri(value: str) -> str:
    value = value.strip()
    if value.startswith("file://"):
        return urllib.parse.unquote(urllib.parse.urlparse(value).path)
    return value


def _looks_like_path(value: str) -> bool:
    value = _path_from_uri(value)
    return bool(
        value.startswith(("/", "~/"))
        or re.match(r"^[A-Za-z]:[\\/]", value)
    )


def _workspace_path_from_value(value: Any, depth: int = 0) -> str:
    """Find an explicit editor workspace path without reading prompt prose."""
    if depth > 8:
        return ""
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith(("{", "[")):
            try:
                return _workspace_path_from_value(json.loads(stripped), depth + 1)
            except Exception:
                return ""
        return _path_from_uri(value) if _looks_like_path(value) else ""
    if isinstance(value, dict):
        preferred_keys = (
            "cwd", "currentWorkingDirectory", "workspaceFolder", "workspacePath",
            "workspaceRoot", "rootPath", "rootUri", "folderUri", "uri", "fsPath",
            "path",
        )
        for key in preferred_keys:
            candidate = value.get(key)
            if isinstance(candidate, str) and _looks_like_path(candidate):
                return _path_from_uri(candidate)
            if isinstance(candidate, dict):
                nested = _workspace_path_from_value(candidate, depth + 1)
                if nested:
                    return nested
        for key in ("workspaceFolders", "folders", "roots"):
            candidate = value.get(key)
            nested = _workspace_path_from_value(candidate, depth + 1)
            if nested:
                return nested
        for child in value.values():
            if isinstance(child, (dict, list)) or (isinstance(child, str) and child.strip().startswith(("{", "["))):
                nested = _workspace_path_from_value(child, depth + 1)
                if nested:
                    return nested
    elif isinstance(value, list):
        for child in value:
            nested = _workspace_path_from_value(child, depth + 1)
            if nested:
                return nested
    return ""


def _latest_pycharm_workspace() -> str:
    logs = sorted(
        (Path.home() / "Library" / "Logs" / "JetBrains").glob("PyCharm*/idea.log"),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    for log_path in logs[:3]:
        try:
            with log_path.open("rb") as handle:
                handle.seek(max(0, log_path.stat().st_size - 2_000_000))
                tail = handle.read().decode("utf-8", errors="replace")
        except Exception:
            continue
        matches = re.findall(r"workspace:\s+file://([^,\s]+)", tail)
        if matches:
            return urllib.parse.unquote(matches[-1])
    return ""


def _workspace_root(path: str) -> str:
    candidate = Path(path).expanduser()
    if candidate.is_file():
        candidate = candidate.parent
    for parent in (candidate, *candidate.parents):
        if (parent / ".git").exists():
            return str(parent)
    return str(candidate)


def _vscode_user_dirs() -> list[Path]:
    """Return VS Code user-data locations for the current operating system."""
    home = Path.home()
    if sys.platform == "darwin":
        base = home / "Library" / "Application Support"
    elif sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or home / "AppData" / "Roaming")
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    return [base / name / "User" for name in ("Code", "Code - Insiders", "VSCodium")]


def _latest_vscode_workspace() -> str:
    """Recover the active VS Code folder from its local workspace state."""
    transcripts = []
    for user_dir in _vscode_user_dirs():
        transcripts.extend(user_dir.glob("workspaceStorage/*/GitHub.copilot-chat/transcripts/*.jsonl"))
    transcripts.sort(key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)
    for transcript in transcripts[:8]:
        storage = transcript.parents[2]
        state_db = storage / "state.vscdb"
        if not state_db.exists():
            continue
        try:
            python = os.environ.get("TRIMP_PYTHON") or shutil.which("python3") or sys.executable
            script = (
                "import sqlite3,sys; "
                "c=sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True,timeout=1); "
                "r=c.execute(\"SELECT value FROM ItemTable WHERE key='workbench.explorer.treeViewState'\").fetchone(); "
                "print(r[0] if r and isinstance(r[0],str) else '')"
            )
            result = subprocess.run([python, "-c", script, str(state_db)], capture_output=True, text=True, timeout=2, check=True)
            payload = json.loads(result.stdout.strip() or "{}")
            focus = payload.get("focus") or payload.get("selection") or []
            if isinstance(focus, list) and focus:
                uri = str(focus[0]).split("::", 1)[0]
                if uri.startswith("file://"):
                    return _workspace_root(urllib.parse.unquote(urllib.parse.urlparse(uri).path))
        except Exception:
            continue
    return ""


def _workspace_context(body: dict[str, Any]) -> dict[str, str]:
    serialized = json.dumps(body, ensure_ascii=False)
    cwd = _workspace_path_from_value(body)
    patterns = (
        r"Current working directory:\s*([^\n<\"]+)",
        r"currentWorkingDirectory[\"']?\s*[:=]\s*[\"']([^\"']+)",
    )
    if not cwd:
        for pattern in patterns:
            match = re.search(pattern, serialized, flags=re.IGNORECASE)
            if match:
                cwd = match.group(1).strip()
                break
    is_vscode = "visual studio code" in serialized.lower() or "vscode" in serialized.lower()
    if not cwd and is_vscode:
        cwd = _latest_vscode_workspace()
    if not cwd:
        cwd = _latest_pycharm_workspace()
    if cwd.startswith("file://"):
        cwd = urllib.parse.unquote(urllib.parse.urlparse(cwd).path)
    cwd = _workspace_root(str(Path(cwd).expanduser())) if cwd else str(PROJECT_ROOT)

    remote = _git_value(cwd, "remote", "get-url", "origin")
    repository = Path(cwd).name
    if remote:
        repository = remote.rstrip("/").rsplit("/", 1)[-1].removesuffix(".git")
    return {
        "cwd": cwd,
        "repository": repository or "unknown",
        "branch": _git_value(cwd, "rev-parse", "--abbrev-ref", "HEAD") or "unknown",
    }


def _post_json(url: str, payload: dict[str, Any]) -> None:
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=raw,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=4) as response:
        if response.status >= 300:
            raise RuntimeError(f"trace endpoint returned {response.status}")


def _spool_trace(payload: dict[str, Any]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with SPOOL_FILE.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, separators=(",", ":"), ensure_ascii=False) + "\n")


def _flush_spool(trace_url: str) -> None:
    if not SPOOL_FILE.exists():
        return
    pending = SPOOL_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
    remaining: list[str] = []
    for index, line in enumerate(pending):
        try:
            payload = json.loads(line)
            _post_json(trace_url, payload)
        except Exception:
            remaining.extend(pending[index:])
            break
    if remaining:
        SPOOL_FILE.write_text("\n".join(remaining) + "\n", encoding="utf-8")
    else:
        SPOOL_FILE.unlink(missing_ok=True)


def _python_is_usable(python: str) -> bool:
    """Check a candidate interpreter is >=3.10 (TrimP's own requires-python)
    and can actually import TrimP, without paying the cost of a real worker
    startup (ChatPayloadOptimizer construction, model warm-up, etc).

    This exists because `shutil.which("python3")` can resolve to whatever
    happens to be first on PATH — on a real machine that's easily an old
    system/framework Python (e.g. 3.9) that predates PEP 604 `X | None`
    union-type syntax used throughout TrimP's compression modules. Under a
    too-old interpreter, importing TrimP crashes at class-definition time,
    which previously surfaced only as a confusing BrokenPipeError/
    JSONDecodeError in the caller — every request failing identically,
    regardless of size or content, because it never even reached the
    request loop.
    """
    try:
        result = subprocess.run(
            [python, "-c", "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"],
            timeout=5,
            capture_output=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def _find_worker_python() -> str:
    """Pick an interpreter for the optimizer_worker subprocess.

    Priority: explicit TRIMP_PYTHON override (trusted as-is, no validation)
    → the project's own .venv/venv (most likely to actually match
    requires-python and have TrimP's dependencies installed) → whatever
    `python3` resolves to on PATH → this process's own interpreter. Each
    non-explicit candidate is version-checked before being accepted so a
    stale system Python doesn't get silently used and fail on every request.
    """
    explicit = os.environ.get("TRIMP_PYTHON")
    if explicit:
        return explicit
    candidates = [
        str(PROJECT_ROOT / ".venv" / "bin" / "python3"),
        str(PROJECT_ROOT / "venv" / "bin" / "python3"),
        shutil.which("python3") or "",
        sys.executable,
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists() and _python_is_usable(candidate):
            return candidate
    # Nothing validated — fall back to the old best-effort behavior so this
    # doesn't hard-fail proxy startup, but the crash (if any) is now at
    # least visible via WORKER_LOG_FILE instead of silently discarded.
    return shutil.which("python3") or sys.executable


class _ExternalOptimizer:
    """Use the normal TrimP runtime outside mitmproxy's restricted Python.

    Homebrew's mitmdump bundles a minimal Python that omits sqlite3 and some
    standard-library modules used by TrimP. The request hook stays lightweight
    and delegates optimization to the project's regular Python interpreter.
    """

    def __init__(self) -> None:
        self.python = _find_worker_python()
        self.timeout = max(3.0, float(os.environ.get("TRIMP_OPTIMIZER_TIMEOUT_SECONDS", "20")))
        self.process: subprocess.Popen[str] | None = None
        self.lock = threading.RLock()
        self.request_id = 0
        self._start()

    def _start(self) -> None:
        if self.process is not None and self.process.poll() is None:
            return
        env = dict(os.environ)
        env["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        # stderr used to go to DEVNULL. If the worker crashed on startup
        # (e.g. an exception constructing ChatPayloadOptimizer, or a fatal
        # error), every subsequent request would fail with a confusing
        # BrokenPipeError/JSONDecodeError and there was no way to see why —
        # the actual traceback was silently discarded. Appending it to a log
        # file instead keeps stdout clean for the JSON-lines protocol while
        # making crashes diagnosable.
        WORKER_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        stderr_log = open(WORKER_LOG_FILE, "a", encoding="utf-8")
        self.process = subprocess.Popen(
            [self.python, "-u", "-m", "TrimP.optimizer_worker"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr_log,
            text=True,
            bufsize=1,
            cwd=str(PROJECT_ROOT),
            env=env,
        )
        stderr_log.close()  # child keeps its own fd; safe to close our copy

    def close(self) -> None:
        process = self.process
        self.process = None
        if process is not None and process.poll() is None:
            process.terminate()

    @staticmethod
    def _fallback_stats(body: dict[str, Any], reason: str) -> dict[str, Any]:
        # The mitmproxy Python cannot use TrimPy's tokenizer stack. A labeled
        # character estimate is still materially more truthful than 0 -> 0.
        estimate = max(1, len(json.dumps(body, separators=(",", ":"), ensure_ascii=False)) // 4)
        return {
            "architecture_version": "context-compiler-v1",
            "tokens_before": estimate,
            "tokens_after": estimate,
            "tokens_saved": 0,
            "savings_pct": 0.0,
            "tokenizer": "chars/4:runtime-fallback-estimate",
            "token_count_exact": False,
            "protected_anchor_retention_pct": 100.0,
            "candidate_anchor_retention_pct": 100.0,
            "fallbacks": [{"path": "$", "method": "optimizer-worker", "reason": reason}],
            "changes": [],
        }

    def _exchange(self, body: dict[str, Any]) -> tuple[dict[str, Any], Any]:
        self._start()
        process = self.process
        if process is None or process.stdin is None or process.stdout is None:
            raise RuntimeError("optimizer worker did not start")
        self.request_id += 1
        request_id = self.request_id
        process.stdin.write(
            json.dumps({"id": request_id, "body": body}, separators=(",", ":"), ensure_ascii=False) + "\n"
        )
        process.stdin.flush()
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ)
        ready = selector.select(self.timeout)
        selector.close()
        if not ready:
            self.close()
            raise TimeoutError(f"optimizer exceeded {self.timeout:.0f}s latency budget")
        payload = json.loads(process.stdout.readline())
        if payload.get("id") != request_id or not payload.get("ok"):
            raise RuntimeError(str(payload.get("error") or "invalid optimizer response"))
        return payload["body"], _Stats(payload["stats"])

    def optimize_body(self, body: dict[str, Any]) -> tuple[dict[str, Any], Any]:
        with self.lock:
            try:
                return self._exchange(body)
            except Exception as exc:
                if ctx is not None:
                    ctx.log.warn(f"TrimP optimizer unavailable; forwarding original payload: {exc}")
                return body, _Stats(self._fallback_stats(body, f"{type(exc).__name__}: {exc}"))


class _Stats:
    def __init__(self, value: dict[str, Any]) -> None:
        self.value = value
        self.tokens_before = int(value.get("tokens_before", 0))
        self.tokens_after = int(value.get("tokens_after", 0))
        self.tokens_saved = int(value.get("tokens_saved", 0))
        self.savings_pct = float(value.get("savings_pct", 0))

    def as_dict(self) -> dict[str, Any]:
        return self.value


class CopilotChatBridge:
    def __init__(self) -> None:
        self.optimizer = _ExternalOptimizer()
        self.requests = 0
        self.tokens_saved = 0
        self.trace_url = os.environ.get("TRIMP_TRACE_URL", DEFAULT_TRACE_URL)

    def load(self, loader: Any) -> None:
        _update_state(
            status="running",
            pid=os.getpid(),
            port=int(os.environ.get("TRIMP_JETBRAINS_PORT", DEFAULT_PORT)),
            started_at=_now_iso(),
            trace_url=self.trace_url,
            ca_cert=str(CA_CERT),
        )

    def done(self) -> None:
        self.optimizer.close()
        _update_state(status="stopped", pid=None)

    def request(self, flow: Any) -> None:
        host = flow.request.pretty_host.lower()
        if host == "trimp.local":
            if flow.request.path.lower().startswith("/probe"):
                _probe_response(flow)
                return
            state = _read_json(STATE_FILE)
            flow.response = http.Response.make(
                200,
                json.dumps({"status": "ok", **state}),
                {"Content-Type": "application/json"},
            )
            return

        path = flow.request.path.lower()
        if not (_is_copilot_host(host) and flow.request.method.upper() == "POST"):
            return

        try:
            original = json.loads(flow.request.get_text(strict=False))
        except Exception:
            return
        if not isinstance(original, dict):
            return
        if not _is_supported_copilot_request(host, path, flow.request.method, original):
            request_source = _request_source(flow, original)
            _update_editor_signal(
                request_source,
                last_unmatched_at=_now_iso(),
                last_unmatched_path=f"{host}{flow.request.path}"[:240],
            )
            _update_state(
                last_unmatched_copilot_at=_now_iso(),
                last_unmatched_copilot=f"{host}{flow.request.path}"[:240],
            )
            if ctx is not None:
                ctx.log.info(f"TrimP skipped unmatched Copilot POST {host}{flow.request.path}")
            return

        optimized, stats = self.optimizer.optimize_body(original)
        prompt = _extract_user_prompt(original)
        optimized_prompt = _extract_user_prompt(optimized)
        request_source = _request_source(flow, original)
        workspace = _workspace_context(original)
        raw_model, model_source = extract_model(original)
        normalized_model = normalize_copilot_model(raw_model, fallback="unknown")
        stats_payload = stats.as_dict()
        stats_payload.update({
            "model_raw": raw_model or None,
            "model_normalized": normalized_model,
            "model_source": model_source,
        })
        metadata = {
            "session_id": _session_id(original, prompt, request_source.split("-", 1)[0]),
            "model": normalized_model,
            "model_raw": raw_model or None,
            "model_source": model_source,
            "stats": stats_payload,
            "user_prompt": prompt,
            "optimized_prompt": optimized_prompt,
            "request_body": original,
            "optimized_body": optimized,
            "workspace_context": workspace,
            "request_source": request_source,
            "host": host,
            "path": flow.request.path,
            "started_at": time.time(),
        }
        flow.metadata["TrimP"] = metadata
        _update_editor_signal(
            request_source,
            last_intercept_at=_now_iso(),
            last_intercept_path=f"{host}{flow.request.path}"[:240],
            last_model=normalized_model,
            last_repository=workspace["repository"],
            last_tokens_before=stats.tokens_before,
            last_tokens_after=stats.tokens_after,
        )

        flow.request.content = json.dumps(
            optimized, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        flow.request.headers.pop("content-encoding", None)
        flow.request.headers["content-type"] = "application/json"

        self.requests += 1
        self.tokens_saved += stats.tokens_saved
        _update_state(
            status="running",
            requests_seen=self.requests,
            tokens_saved=self.tokens_saved,
            last_request_at=_now_iso(),
            last_model=metadata["model"],
            last_repository=workspace["repository"],
            last_tokens_before=stats.tokens_before,
            last_tokens_after=stats.tokens_after,
        )
        if ctx is not None:
            ctx.log.info(
                f"TrimP {host}{flow.request.path}: {stats.tokens_before} -> "
                f"{stats.tokens_after} tokens ({stats.savings_pct:.2f}% saved)"
            )

    def response(self, flow: Any) -> None:
        metadata = flow.metadata.get("TrimP")
        if not isinstance(metadata, dict):
            return
        text = flow.response.get_text(strict=False) if flow.response else ""
        content_type = flow.response.headers.get("content-type", "") if flow.response else ""
        response_body, assistant, actual_usage = _parse_response(text, content_type)
        elapsed_ms = round((time.time() - float(metadata.pop("started_at", time.time()))) * 1000)
        debug_excerpt = (
            "TrimPy IDE HTTPS bridge\n"
            f"client={metadata.get('request_source', 'ide-copilot-chat')}\n"
            f"host={metadata.pop('host')}\n"
            f"path={metadata.pop('path')}\n"
            f"status={flow.response.status_code if flow.response else 'no-response'}\n"
            f"elapsed_ms={elapsed_ms}\n"
            f"response_bytes={len(text.encode('utf-8', errors='replace'))}\n"
            f"model_raw={metadata.get('model_raw') or 'unavailable'}\n"
            f"model_normalized={metadata.get('model') or 'unknown'}\n"
            f"model_source={metadata.get('model_source') or 'unavailable'}\n"
            f"workspace={metadata['workspace_context'].get('cwd', 'unknown')}"
        )
        trace = {
            **metadata,
            "assistant_response": assistant,
            "response_body": response_body,
            "actual_usage": actual_usage,
            "debug_log_excerpt": debug_excerpt,
        }
        try:
            _post_json(self.trace_url, trace)
            _flush_spool(self.trace_url)
            _update_state(last_trace_status="recorded", last_trace_at=_now_iso())
            _update_editor_signal(
                metadata.get("request_source", "ide-copilot-chat"),
                last_logged_at=_now_iso(),
                last_trace_status="recorded",
            )
        except Exception as exc:
            _spool_trace(trace)
            _update_state(last_trace_status=f"spooled: {exc}", last_trace_at=_now_iso())
            _update_editor_signal(
                metadata.get("request_source", "ide-copilot-chat"),
                last_trace_status=f"spooled: {exc}",
            )


addons = [CopilotChatBridge()]


def find_mitmdump() -> str | None:
    configured = os.environ.get("TRIMP_MITMDUMP")
    if configured and Path(configured).is_file():
        return configured
    return shutil.which("mitmdump")


def _pid() -> int | None:
    try:
        return int(PID_FILE.read_text(encoding="utf-8").strip())
    except Exception:
        return None


def _pid_alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _proxy_command(host: str, port: int) -> list[str]:
    mitmdump = find_mitmdump()
    if not mitmdump:
        raise RuntimeError(
            "mitmdump is not installed. On macOS run: brew install --cask mitmproxy"
        )
    return [
        mitmdump,
        "--listen-host",
        host,
        "--listen-port",
        str(port),
        "--set",
        f"confdir={MITM_DIR}",
        "--set",
        "connection_strategy=lazy",
        "--set",
        "flow_detail=0",
        "--set",
        "show_ignored_hosts=false",
        "--set",
        f"allow_hosts={COPILOT_HOST_PATTERN}",
        "--set",
        "termlog_verbosity=info",
        "-s",
        str(Path(__file__).resolve()),
    ]


def start_proxy(
    host: str = "127.0.0.1",
    port: int = DEFAULT_PORT,
    *,
    background: bool = True,
) -> dict[str, Any]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    MITM_DIR.mkdir(parents=True, exist_ok=True)
    existing = _pid()
    if _pid_alive(existing):
        return {"started": False, "pid": existing, "status": "already-running"}

    command = _proxy_command(host, port)
    env = dict(os.environ)
    env["TRIMP_JETBRAINS_PORT"] = str(port)
    env.setdefault("TRIMP_TRACE_URL", DEFAULT_TRACE_URL)
    if not background:
        return {"started": True, "exit_code": subprocess.call(command, env=env)}

    log_handle = LOG_FILE.open("ab")
    process = subprocess.Popen(
        command,
        env=env,
        stdin=subprocess.DEVNULL,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    log_handle.close()
    PID_FILE.write_text(str(process.pid), encoding="utf-8")
    for _ in range(50):
        if process.poll() is not None:
            break
        try:
            with socket.create_connection((host, port), timeout=0.15):
                _update_state(status="running", pid=process.pid, host=host, port=port)
                return {"started": True, "pid": process.pid, "status": "running"}
        except OSError:
            time.sleep(0.1)
    tail = ""
    try:
        tail = "\n".join(LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-20:])
    except Exception:
        pass
    raise RuntimeError(f"JetBrains bridge failed to start.\n{tail}")


def stop_proxy() -> dict[str, Any]:
    pid = _pid()
    if not _pid_alive(pid):
        PID_FILE.unlink(missing_ok=True)
        _update_state(status="stopped", pid=None)
        return {"stopped": False, "status": "not-running"}
    os.kill(pid, signal.SIGTERM)
    for _ in range(50):
        if not _pid_alive(pid):
            break
        time.sleep(0.1)
    if _pid_alive(pid):
        os.kill(pid, signal.SIGKILL)
    PID_FILE.unlink(missing_ok=True)
    _update_state(status="stopped", pid=None)
    return {"stopped": True, "pid": pid, "status": "stopped"}


def proxy_status() -> dict[str, Any]:
    state = _read_json(STATE_FILE)
    pid = _pid()
    state.update(
        {
            "running": _pid_alive(pid),
            "pid": pid if _pid_alive(pid) else None,
            "mitmdump": find_mitmdump(),
            "ca_cert": str(CA_CERT),
            "ca_exists": CA_CERT.exists(),
            "ca_trusted": ca_is_trusted(),
            "log_file": str(LOG_FILE),
            "spooled_traces": sum(1 for _ in SPOOL_FILE.open()) if SPOOL_FILE.exists() else 0,
            "configured_ides": configured_ides(),
        }
    )
    return state


def _integration_for_editor(editor: str) -> str:
    value = str(editor or "").lower()
    if "vs" in value or "code" in value:
        return "vscode-chat"
    if "rider" in value:
        return "rider-chat"
    return "pycharm-chat"


def probe_proxy(editor: str = "pycharm", host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> dict[str, Any]:
    """Send a localhost-only probe through the IDE proxy.

    This verifies the editor proxy path can intercept HTTP traffic. It never
    contacts GitHub because mitmproxy handles ``TrimP.local`` locally.
    """
    payload = {
        "model": "trimp-probe",
        "messages": [{"role": "user", "content": "trimp-probe"}],
        "stream": False,
    }
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        "http://TrimP.local/probe",
        data=raw,
        headers={
            "Content-Type": "application/json",
            "X-GitHub-Copilot-Integration-Id": _integration_for_editor(editor),
            "X-Client-Name": str(editor or "editor"),
        },
        method="POST",
    )
    request.set_proxy(f"{host}:{port}", "http")
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=3) as response:
            body = response.read().decode("utf-8", errors="replace")
            data = json.loads(body or "{}")
            return {
                "editor": editor,
                "status": "up" if data.get("intercepted") else "degraded",
                "intercepted": bool(data.get("intercepted")),
                "request_source": data.get("request_source"),
                "model": data.get("model"),
                "payload_ok": bool(data.get("payload_ok")),
                "http_status": response.status,
            }
    except Exception as exc:
        return {
            "editor": editor,
            "status": "down",
            "intercepted": False,
            "error": str(exc)[:160],
        }


def ca_is_trusted() -> bool:
    if sys.platform != "darwin" or not CA_CERT.exists():
        return False
    result = subprocess.run(
        ["security", "verify-cert", "-c", str(CA_CERT), "-p", "basic"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def trust_ca() -> dict[str, Any]:
    if sys.platform != "darwin":
        raise RuntimeError("Automatic certificate trust is currently implemented for macOS only")
    if not CA_CERT.exists():
        was_running = _pid_alive(_pid())
        start_proxy()
        for _ in range(50):
            if CA_CERT.exists():
                break
            time.sleep(0.1)
        if not was_running:
            stop_proxy()
    if not CA_CERT.exists():
        raise RuntimeError("mitmproxy did not generate its CA certificate")
    keychain = Path.home() / "Library" / "Keychains" / "login.keychain-db"
    result = subprocess.run(
        [
            "security",
            "add-trusted-cert",
            "-r",
            "trustRoot",
            "-p",
            "ssl",
            "-p",
            "basic",
            "-k",
            str(keychain),
            str(CA_CERT),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "trusted": result.returncode == 0 and ca_is_trusted(),
        "return_code": result.returncode,
        "message": (result.stderr or result.stdout).strip(),
        "certificate": str(CA_CERT),
    }


def _jetbrains_config_roots() -> list[Path]:
    """Return JetBrains configuration roots on macOS, Windows, and Linux."""
    home = Path.home()
    if sys.platform == "darwin":
        roots = [home / "Library" / "Application Support" / "JetBrains"]
    elif sys.platform == "win32":
        roots = [Path(os.environ.get("APPDATA") or home / "AppData" / "Roaming") / "JetBrains"]
    else:
        roots = [Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config") / "JetBrains"]
    return roots


def _ide_config_paths() -> list[Path]:
    paths = []
    for root in _jetbrains_config_roots():
        paths.extend(root.glob("*/options/github-copilot.xml"))
    return sorted(paths, key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True)


def _option(component: ET.Element, name: str) -> ET.Element | None:
    return component.find(f"./option[@name='{name}']")


def _selected_config(config_path: str | None = None) -> Path:
    if config_path:
        path = Path(config_path).expanduser().resolve()
        if not path.exists():
            raise RuntimeError(f"Copilot settings file not found: {path}")
        return path
    paths = _ide_config_paths()
    if not paths:
        raise RuntimeError("No JetBrains GitHub Copilot settings file was found")
    return paths[0]


def configure_ide(port: int = DEFAULT_PORT, config_path: str | None = None) -> dict[str, Any]:
    import xml.etree.ElementTree as ET

    path = _selected_config(config_path)
    tree = ET.parse(path)
    root = tree.getroot()
    component = root.find("./component[@name='github-copilot']")
    if component is None:
        component = ET.SubElement(root, "component", {"name": "github-copilot"})

    config_state = _read_json(CONFIG_STATE_FILE)
    entries = config_state.setdefault("files", {})
    entry = entries.setdefault(str(path), {"previous": {}})
    previous = entry["previous"]
    desired = dict(PROXY_OPTIONS)
    desired["customHttpProxyPort"] = str(port)
    for name, value in desired.items():
        current = _option(component, name)
        if name not in previous:
            previous[name] = {
                "present": current is not None,
                "value": current.get("value") if current is not None else None,
            }
        if current is None:
            current = ET.SubElement(component, "option", {"name": name})
        current.set("value", value)

    backup_dir = DATA_DIR / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    if "backup" not in entry:
        backup = backup_dir / f"{path.parents[1].name}-github-copilot.xml"
        shutil.copy2(path, backup)
        entry["backup"] = str(backup)
    entry.update({"configured_at": _now_iso(), "host": "127.0.0.1", "port": port})
    _write_json(CONFIG_STATE_FILE, config_state)

    ET.indent(tree, space="  ")
    temp = path.with_suffix(".xml.trimp-tmp")
    tree.write(temp, encoding="unicode", xml_declaration=False)
    with temp.open("a", encoding="utf-8") as handle:
        handle.write("\n")
    os.replace(temp, path)
    # Rider routes Copilot through the IDE-wide HttpConfigurable settings,
    # while PyCharm honors the Copilot-specific options above.
    if "Rider" in str(path):
        proxy_path = path.parent / "proxy.settings.xml"
        proxy_tree = ET.parse(proxy_path) if proxy_path.exists() else ET.ElementTree(ET.Element("application"))
        proxy_root = proxy_tree.getroot()
        http_component = proxy_root.find("./component[@name='HttpConfigurable']")
        if http_component is None:
            http_component = ET.SubElement(proxy_root, "component", {"name": "HttpConfigurable"})
        desired_proxy = {
            "USE_HTTP_PROXY": "true",
            "USE_PROXY_PAC": "false",
            "PROXY_HOST": "127.0.0.1",
            "PROXY_PORT": str(port),
            "PROXY_TYPE_IS_SOCKS": "false",
        }
        for name, value in desired_proxy.items():
            option = _option(http_component, name)
            if option is None:
                option = ET.SubElement(http_component, "option", {"name": name})
            option.set("value", value)
        ET.indent(proxy_tree, space="  ")
        proxy_temp = proxy_path.with_suffix(".xml.trimp-tmp")
        proxy_tree.write(proxy_temp, encoding="unicode", xml_declaration=False)
        with proxy_temp.open("a", encoding="utf-8") as handle:
            handle.write("\n")
        os.replace(proxy_temp, proxy_path)
    return {
        "configured": True,
        "path": str(path),
        "host": "127.0.0.1",
        "port": port,
        "restart_required": True,
        "backup": entry["backup"],
    }


def unconfigure_ide(config_path: str | None = None) -> dict[str, Any]:
    import xml.etree.ElementTree as ET

    path = _selected_config(config_path)
    config_state = _read_json(CONFIG_STATE_FILE)
    entry = config_state.get("files", {}).get(str(path))
    if not isinstance(entry, dict):
        return {"restored": False, "path": str(path), "status": "not-configured-by-TrimP"}

    tree = ET.parse(path)
    component = tree.getroot().find("./component[@name='github-copilot']")
    if component is None:
        return {"restored": False, "path": str(path), "status": "component-missing"}
    for name, prior in entry.get("previous", {}).items():
        current = _option(component, name)
        if prior.get("present"):
            if current is None:
                current = ET.SubElement(component, "option", {"name": name})
            current.set("value", str(prior.get("value") or ""))
        elif current is not None:
            component.remove(current)

    ET.indent(tree, space="  ")
    temp = path.with_suffix(".xml.trimp-tmp")
    tree.write(temp, encoding="unicode", xml_declaration=False)
    with temp.open("a", encoding="utf-8") as handle:
        handle.write("\n")
    os.replace(temp, path)
    del config_state["files"][str(path)]
    _write_json(CONFIG_STATE_FILE, config_state)
    return {"restored": True, "path": str(path), "restart_required": True}


def configured_ides() -> list[dict[str, Any]]:
    import xml.etree.ElementTree as ET

    output = []
    for path in _ide_config_paths():
        try:
            root = ET.parse(path).getroot()
            component = root.find("./component[@name='github-copilot']")
            enabled = _option(component, "customHttpProxyEnabled") if component is not None else None
            host = _option(component, "customHttpProxyHost") if component is not None else None
            port = _option(component, "customHttpProxyPort") if component is not None else None
            proxy_path = path.parent / "proxy.settings.xml"
            global_proxy = False
            if "Rider" in str(path) and proxy_path.exists():
                proxy_root = ET.parse(proxy_path).getroot()
                http_component = proxy_root.find("./component[@name='HttpConfigurable']")
                global_proxy = (
                    _option(http_component, "USE_HTTP_PROXY") is not None
                    and _option(http_component, "USE_HTTP_PROXY").get("value") == "true"
                    and _option(http_component, "PROXY_HOST") is not None
                    and _option(http_component, "PROXY_PORT") is not None
                )
            if (enabled is not None and enabled.get("value") == "true") or global_proxy:
                if global_proxy:
                    host = _option(http_component, "PROXY_HOST")
                    port = _option(http_component, "PROXY_PORT")
                output.append(
                    {
                        "product": path.parents[1].name,
                        "path": str(path),
                        "host": host.get("value") if host is not None else "",
                        "port": int(port.get("value") or 0) if port is not None else 0,
                    }
                )
        except Exception:
            continue
    return output


def vscode_settings_path() -> Path:
    """Select the first existing VS Code-family settings file, cross-platform."""
    candidates = [user_dir / "settings.json" for user_dir in _vscode_user_dirs()]
    return next((path for path in candidates if path.exists()), candidates[0])


def configure_vscode(port: int = DEFAULT_PORT, settings_path: str | None = None) -> dict[str, Any]:
    path = Path(settings_path).expanduser() if settings_path else vscode_settings_path()
    if not path.exists():
        raise RuntimeError(f"VS Code settings file not found: {path}")
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"VS Code settings.json is not valid JSON: {exc}") from exc
    if not isinstance(settings, dict):
        raise RuntimeError("VS Code settings.json must contain an object")
    backup = DATA_DIR / "backups" / "vscode-settings.json"
    backup.parent.mkdir(parents=True, exist_ok=True)
    if not backup.exists():
        shutil.copy2(path, backup)
    settings["http.proxy"] = f"http://127.0.0.1:{port}"
    settings["http.proxyStrictSSL"] = False
    settings["http.proxySupport"] = "override"
    temp = path.with_suffix(".json.trimp-tmp")
    temp.write_text(json.dumps(settings, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(temp, path)
    _update_state(vscode_configured=True, vscode_settings=str(path), vscode_port=port)
    return {"configured": True, "path": str(path), "port": port, "backup": str(backup), "restart_required": True}


def unconfigure_vscode(settings_path: str | None = None) -> dict[str, Any]:
    path = Path(settings_path).expanduser() if settings_path else vscode_settings_path()
    backup = DATA_DIR / "backups" / "vscode-settings.json"
    if not backup.exists():
        return {"restored": False, "path": str(path), "status": "no-TrimP-backup"}
    shutil.copy2(backup, path)
    _update_state(vscode_configured=False, vscode_settings=str(path))
    return {"restored": True, "path": str(path), "backup": str(backup), "restart_required": True}
