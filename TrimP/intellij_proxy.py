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
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
SPOOL_FILE = DATA_DIR / "trace-spool.jsonl"
CONFIG_STATE_FILE = DATA_DIR / "ide-config.json"
DEFAULT_PORT = 8767
DEFAULT_TRACE_URL = "http://127.0.0.1:8766/v1/TrimP/trace"
CA_CERT = MITM_DIR / "mitmproxy-ca-cert.pem"

COPILOT_HOST_PATTERN = (
    r"(^|\.)githubcopilot\.com(:[0-9]+)?$|"
    r"^copilot-proxy\.githubusercontent\.com(:[0-9]+)?$|"
    r"^TrimP\.local(:[0-9]+)?$"
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


def _session_id(body: dict[str, Any], prompt: str) -> str:
    key = _recursive_value(body, SESSION_KEYS)
    if not key:
        seed = prompt or json.dumps(body.get("model", "unknown"))
        key = hashlib.sha256(seed.encode("utf-8", errors="replace")).hexdigest()[:20]
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", key).strip("-")[:120]
    return f"jetbrains-{safe or 'chat'}"


def _git_value(cwd: str, *args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=cwd, stderr=subprocess.DEVNULL, text=True, timeout=2
        ).strip()
    except Exception:
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


def _workspace_context(body: dict[str, Any]) -> dict[str, str]:
    serialized = json.dumps(body, ensure_ascii=False)
    patterns = (
        r"Current working directory:\s*([^\n<\"]+)",
        r"currentWorkingDirectory[\"']?\s*[:=]\s*[\"']([^\"']+)",
    )
    cwd = ""
    for pattern in patterns:
        match = re.search(pattern, serialized, flags=re.IGNORECASE)
        if match:
            cwd = match.group(1).strip()
            break
    if not cwd:
        cwd = _latest_pycharm_workspace()
    if cwd.startswith("file://"):
        cwd = urllib.parse.unquote(urllib.parse.urlparse(cwd).path)
    cwd = str(Path(cwd).expanduser()) if cwd else str(PROJECT_ROOT)

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


class _ExternalOptimizer:
    """Use the normal TrimP runtime outside mitmproxy's restricted Python.

    Homebrew's mitmdump bundles a minimal Python that omits sqlite3 and some
    standard-library modules used by TrimP. The request hook stays lightweight
    and delegates optimization to the project's regular Python interpreter.
    """

    _SCRIPT = (
        "import json,sys; "
        "from TrimP.chat_optimizer import ChatPayloadOptimizer; "
        "body=json.load(sys.stdin); optimized,stats=ChatPayloadOptimizer().optimize_body(body); "
        "json.dump({'body':optimized,'stats':stats.as_dict()},sys.stdout,separators=(',',':'))"
    )

    def __init__(self) -> None:
        self.python = os.environ.get("TRIMP_PYTHON") or shutil.which("python3") or sys.executable

    def optimize_body(self, body: dict[str, Any]) -> tuple[dict[str, Any], Any]:
        env = dict(os.environ)
        env["PYTHONPATH"] = str(PROJECT_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        try:
            result = subprocess.run(
                [self.python, "-c", self._SCRIPT],
                input=json.dumps(body, ensure_ascii=False),
                text=True,
                capture_output=True,
                timeout=12,
                cwd=str(PROJECT_ROOT),
                env=env,
                check=True,
            )
            payload = json.loads(result.stdout)
            return payload["body"], _Stats(payload["stats"])
        except Exception as exc:
            if ctx is not None:
                ctx.log.warn(f"TrimP optimizer unavailable; forwarding original payload: {exc}")
            return body, _Stats({"tokens_before": 0, "tokens_after": 0, "tokens_saved": 0, "savings_pct": 0, "changes": []})


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
        _update_state(status="stopped", pid=None)

    def request(self, flow: Any) -> None:
        host = flow.request.pretty_host.lower()
        if host == "TrimP.local":
            state = _read_json(STATE_FILE)
            flow.response = http.Response.make(
                200,
                json.dumps({"status": "ok", **state}),
                {"Content-Type": "application/json"},
            )
            return

        path = flow.request.path.lower()
        if not (
            (host.endswith("githubcopilot.com") or host == "copilot-proxy.githubusercontent.com")
            and flow.request.method.upper() == "POST"
            and ("/chat/completions" in path or path.endswith("/responses"))
        ):
            return

        try:
            original = json.loads(flow.request.get_text(strict=False))
        except Exception:
            return
        if not isinstance(original, dict):
            return

        optimized, stats = self.optimizer.optimize_body(original)
        prompt = _extract_user_prompt(original)
        optimized_prompt = _extract_user_prompt(optimized)
        workspace = _workspace_context(original)
        metadata = {
            "session_id": _session_id(original, prompt),
            "model": str(original.get("model") or "unknown"),
            "stats": stats.as_dict(),
            "user_prompt": prompt,
            "optimized_prompt": optimized_prompt,
            "request_body": original,
            "optimized_body": optimized,
            "workspace_context": workspace,
            "request_source": "pycharm-copilot-chat",
            "host": host,
            "path": flow.request.path,
            "started_at": time.time(),
        }
        flow.metadata["TrimP"] = metadata

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
            "JetBrains Copilot TLS bridge\n"
            f"host={metadata.pop('host')}\n"
            f"path={metadata.pop('path')}\n"
            f"status={flow.response.status_code if flow.response else 'no-response'}\n"
            f"elapsed_ms={elapsed_ms}\n"
            f"response_bytes={len(text.encode('utf-8', errors='replace'))}\n"
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
        except Exception as exc:
            _spool_trace(trace)
            _update_state(last_trace_status=f"spooled: {exc}", last_trace_at=_now_iso())


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


def _ide_config_paths() -> list[Path]:
    root = Path.home() / "Library" / "Application Support" / "JetBrains"
    return sorted(root.glob("*/options/github-copilot.xml"), reverse=True)


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
        raise RuntimeError("No PyCharm GitHub Copilot settings file was found")
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
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Code" / "User" / "settings.json"
    return Path.home() / ".config" / "Code" / "User" / "settings.json"


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
