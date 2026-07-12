"""GitHub Copilot Enterprise auth helpers for TrimP BYOK integration.

Copilot Enterprise does not give users a static model API key. The official
clients authenticate the user with GitHub, then exchange that reusable GitHub
OAuth token for a short-lived Copilot API bearer token. This module mirrors the
small part of that flow needed by the local TrimP proxy.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import ssl
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error as urllib_error
from urllib import request as urllib_request
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

try:
    import certifi
except Exception:  # pragma: no cover - certifi ships with the local deps here.
    certifi = None

DEFAULT_API_URL = "https://api.githubcopilot.com"
DEFAULT_TOKEN_EXCHANGE_URL = "https://api.github.com/copilot_internal/v2/token"
DEFAULT_USER_INFO_URL = "https://api.github.com/copilot_internal/user"
DEFAULT_GITHUB_HOST = "github.com"
_TOKEN_EXPIRY_BUFFER_S = 60

_DEFAULT_EDITOR_VERSION = "vscode/1.107.0"
_DEFAULT_USER_AGENT = "GitHubCopilotChat/0.35.0"
_DEFAULT_EDITOR_PLUGIN_VERSION = "copilot-chat/0.35.0"
_DEFAULT_COPILOT_INTEGRATION_ID = "vscode-chat"

_API_TOKEN_ENV_VARS = ("GITHUB_COPILOT_API_TOKEN", "COPILOT_PROVIDER_BEARER_TOKEN")
_OAUTH_TOKEN_ENV_VARS = (
    "GITHUB_COPILOT_GITHUB_TOKEN",
    "GITHUB_COPILOT_TOKEN",
    "COPILOT_GITHUB_TOKEN",
)
_GENERIC_GITHUB_TOKEN_ENV_VARS = ("GH_TOKEN", "GITHUB_TOKEN")
_OAUTH_TOKEN_KEYS = ("oauth_token", "oauthToken", "token", "access_token", "accessToken")
_EXPIRY_KEYS = ("expires_at", "expiresAt", "expiry", "expires")


@dataclass(frozen=True)
class CopilotAPIToken:
    token: str
    expires_at: float
    api_url: str = DEFAULT_API_URL
    source: str = "unknown"

    @property
    def is_valid(self) -> bool:
        return time.time() < (self.expires_at - _TOKEN_EXPIRY_BUFFER_S)


@dataclass(frozen=True)
class TokenCandidate:
    token: str
    source: str


def _github_host() -> str:
    return (os.environ.get("GITHUB_COPILOT_HOST") or DEFAULT_GITHUB_HOST).strip().lower()


def _enterprise_hostname(value: str) -> str:
    normalized = value.strip().replace("https://", "").replace("http://", "").rstrip("/")
    if not normalized:
        return ""
    parsed = urlparse(f"https://{normalized}")
    return (parsed.hostname or normalized.split("/", 1)[0]).lower()


def _configured_enterprise_domain() -> str | None:
    raw = (
        os.environ.get("GITHUB_COPILOT_ENTERPRISE_URL", "").strip()
        or os.environ.get("GITHUB_COPILOT_ENTERPRISE_DOMAIN", "").strip()
    )
    if not raw:
        return None
    host = _enterprise_hostname(raw)
    for prefix in ("copilot-api.", "api."):
        if host.startswith(prefix):
            host = host[len(prefix) :]
            break
    if host in {"", "github.com", "www.github.com", "api.github.com"}:
        return None
    return host


def get_copilot_api_url() -> str:
    configured = os.environ.get("GITHUB_COPILOT_API_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    enterprise_domain = _configured_enterprise_domain()
    if enterprise_domain:
        return f"https://copilot-api.{enterprise_domain}"
    return DEFAULT_API_URL


def _token_exchange_url() -> str:
    configured = os.environ.get("GITHUB_COPILOT_TOKEN_EXCHANGE_URL", "").strip()
    if configured:
        return configured
    enterprise_domain = _configured_enterprise_domain()
    if enterprise_domain:
        return f"https://api.{enterprise_domain}/copilot_internal/v2/token"
    return DEFAULT_TOKEN_EXCHANGE_URL


def _user_info_url() -> str:
    configured = os.environ.get("GITHUB_COPILOT_USER_INFO_URL", "").strip()
    if configured:
        return configured
    enterprise_domain = _configured_enterprise_domain()
    if enterprise_domain:
        return f"https://api.{enterprise_domain}/copilot_internal/user"
    return DEFAULT_USER_INFO_URL


def _copilot_headers(token: str | None = None) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "User-Agent": os.environ.get("GITHUB_COPILOT_USER_AGENT", _DEFAULT_USER_AGENT).strip()
        or _DEFAULT_USER_AGENT,
        "Editor-Version": os.environ.get(
            "GITHUB_COPILOT_EDITOR_VERSION", _DEFAULT_EDITOR_VERSION
        ).strip()
        or _DEFAULT_EDITOR_VERSION,
        "Editor-Plugin-Version": os.environ.get(
            "GITHUB_COPILOT_EDITOR_PLUGIN_VERSION", _DEFAULT_EDITOR_PLUGIN_VERSION
        ).strip()
        or _DEFAULT_EDITOR_PLUGIN_VERSION,
        "Copilot-Integration-Id": os.environ.get(
            "GITHUB_COPILOT_INTEGRATION_ID", _DEFAULT_COPILOT_INTEGRATION_ID
        ).strip()
        or _DEFAULT_COPILOT_INTEGRATION_ID,
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def copilot_request_headers(token: str) -> dict[str, str]:
    headers = _copilot_headers(token)
    headers["Content-Type"] = "application/json"
    return headers


def is_copilot_api_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url)
    host = (parsed.hostname or parsed.netloc or parsed.path.split("/", 1)[0]).lower()
    configured_host = urlparse(get_copilot_api_url()).hostname
    if configured_host and host == configured_host.lower():
        return True
    return host == "githubcopilot.com" or host.endswith(".githubcopilot.com") or (
        host.startswith("copilot-api.") and host.endswith(".ghe.com")
    )


def build_copilot_upstream_url(base_url: str, path: str) -> str:
    normalized_base = base_url.rstrip("/")
    normalized_path = path if path.startswith("/") else f"/{path}"
    if is_copilot_api_url(normalized_base) and normalized_path.startswith("/v1/"):
        normalized_path = normalized_path[3:]
    return f"{normalized_base}{normalized_path}"


def _is_copilot_api_token(token: str) -> bool:
    token = token.strip()
    if not token:
        return False
    if token.startswith(("gho_", "ghs_", "ghp_", "github_pat_")):
        return False
    return token.startswith("tid_")


def _parse_expiry(value: Any) -> float | None:
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number / 1000.0 if number > 10_000_000_000 else number
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        if raw.isdigit():
            return _parse_expiry(int(raw))
        try:
            return datetime.fromisoformat(raw.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def _entry_expired(entry: dict[str, Any]) -> bool:
    for key in _EXPIRY_KEYS:
        expiry = _parse_expiry(entry.get(key))
        if expiry is not None:
            return time.time() >= (expiry - _TOKEN_EXPIRY_BUFFER_S)
    return False


def _extract_oauth_token(entry: dict[str, Any]) -> str | None:
    if _entry_expired(entry):
        return None
    for key in _OAUTH_TOKEN_KEYS:
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    for value in entry.values():
        if isinstance(value, dict):
            nested = _extract_oauth_token(value)
            if nested:
                return nested
    return None


def _read_copilot_config_login() -> str | None:
    path = Path(os.environ.get("COPILOT_HOME", str(Path.home() / ".copilot"))) / "config.json"
    try:
        lines = [
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("//")
        ]
        payload = json.loads("\n".join(lines))
    except Exception:
        return None
    user = payload.get("lastLoggedInUser") if isinstance(payload, dict) else None
    login = user.get("login") if isinstance(user, dict) else None
    return login.strip() if isinstance(login, str) and login.strip() else None


def _run_security_lookup(command: list[str]) -> str | None:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    token = result.stdout.strip()
    return token if result.returncode == 0 and token else None


def _read_macos_keychain_token() -> str | None:
    if sys.platform != "darwin":
        return None
    host = _github_host()
    login = _read_copilot_config_login()
    services = [
        "GitHub Copilot",
        "GitHub Copilot CLI",
        "github-copilot",
        "copilot",
        "copilot-cli",
        "GitHub CLI",
        "github.com",
        f"https://{host}",
        host,
    ]
    accounts = [
        value
        for value in (
            f"https://{host}:{login}" if login else None,
            f"{host}:{login}" if login else None,
            login,
            os.environ.get("USER"),
            os.environ.get("USERNAME"),
            host,
            f"https://{host}",
        )
        if value
    ]
    for service in services:
        token = _run_security_lookup(["security", "find-generic-password", "-s", service, "-w"])
        if token:
            return token
        for account in accounts:
            token = _run_security_lookup(
                ["security", "find-generic-password", "-s", service, "-a", account, "-w"]
            )
            if token:
                return token
    for server in (host, f"https://{host}"):
        token = _run_security_lookup(["security", "find-internet-password", "-s", server, "-w"])
        if token:
            return token
    return None


def _read_gh_cli_token() -> str | None:
    command = [os.environ.get("GH_PATH", "").strip() or "gh", "auth", "token"]
    host = _github_host()
    if host and host != DEFAULT_GITHUB_HOST:
        command.extend(["--hostname", host])
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False, timeout=8)
    except (OSError, subprocess.TimeoutExpired):
        return None
    token = result.stdout.strip()
    return token if result.returncode == 0 and token else None


def _read_file_candidates() -> list[TokenCandidate]:
    paths: list[Path] = []
    override = os.environ.get("GITHUB_COPILOT_TOKEN_FILE", "").strip()
    if override:
        paths.append(Path(override).expanduser())
    paths.extend(
        [
            Path.home() / ".config" / "github-copilot" / "apps.json",
            Path.home() / ".config" / "github-copilot" / "hosts.json",
        ]
    )
    candidates: list[TokenCandidate] = []
    host = _github_host()
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        entries: list[tuple[str, dict[str, Any]]] = []
        if isinstance(payload, dict):
            entries = [(str(k), v) for k, v in payload.items() if isinstance(v, dict)]
        elif isinstance(payload, list):
            entries = [
                (str(v.get("host") or v.get("githubHost") or i), v)
                for i, v in enumerate(payload)
                if isinstance(v, dict)
            ]
        for key, entry in entries:
            if host not in key.lower():
                continue
            token = _extract_oauth_token(entry)
            if token:
                candidates.append(TokenCandidate(token, f"file:{path}"))
    return candidates


def iter_oauth_token_candidates() -> list[TokenCandidate]:
    candidates: list[TokenCandidate] = []
    for env_var in _OAUTH_TOKEN_ENV_VARS:
        token = os.environ.get(env_var, "").strip()
        if token:
            candidates.append(TokenCandidate(token, f"env:{env_var}"))
    keychain_token = _read_macos_keychain_token()
    if keychain_token:
        candidates.append(TokenCandidate(keychain_token, "macos-keychain"))
    candidates.extend(_read_file_candidates())
    for env_var in _GENERIC_GITHUB_TOKEN_ENV_VARS:
        token = os.environ.get(env_var, "").strip()
        if token:
            candidates.append(TokenCandidate(token, f"env:{env_var}"))
    gh_token = _read_gh_cli_token()
    if gh_token:
        candidates.append(TokenCandidate(gh_token, "gh-cli"))

    seen: set[str] = set()
    deduped: list[TokenCandidate] = []
    for candidate in candidates:
        if candidate.token in seen:
            continue
        seen.add(candidate.token)
        deduped.append(candidate)
    return deduped


def _fetch_user_info(token: str) -> dict[str, Any] | None:
    request = urllib_request.Request(_user_info_url(), headers=_copilot_headers(token), method="GET")
    try:
        with urllib_request.urlopen(request, timeout=10.0, context=_ssl_context()) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except Exception as exc:
        logger.debug("Copilot user info lookup failed: %s", exc)
        return None
    return payload if isinstance(payload, dict) else None


def _api_url_from_payload(payload: dict[str, Any] | None) -> str | None:
    endpoints = payload.get("endpoints") if isinstance(payload, dict) else None
    api_url = endpoints.get("api") if isinstance(endpoints, dict) else None
    return api_url.strip().rstrip("/") if isinstance(api_url, str) and api_url.strip() else None


def _exchange_token_sync(oauth_token: str) -> CopilotAPIToken:
    request = urllib_request.Request(
        _token_exchange_url(),
        headers=_copilot_headers(oauth_token),
        method="GET",
    )
    try:
        with urllib_request.urlopen(request, timeout=10.0, context=_ssl_context()) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except urllib_error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Copilot token exchange failed with HTTP {exc.code}: {body}") from exc

    if not isinstance(payload, dict):
        raise RuntimeError("Copilot token exchange returned an invalid payload.")
    token = str(payload.get("token") or "").strip()
    if not token:
        raise RuntimeError("Copilot token exchange returned an empty token.")
    expires_at = _parse_expiry(payload.get("expires_at")) or (time.time() + 1800)
    api_url = _api_url_from_payload(payload) or get_copilot_api_url()
    if not is_copilot_api_url(api_url):
        api_url = get_copilot_api_url()
    return CopilotAPIToken(token=token, expires_at=expires_at, api_url=api_url, source="token-exchange")


def _ssl_context() -> ssl.SSLContext | None:
    if certifi is None:
        return None
    return ssl.create_default_context(cafile=certifi.where())


class CopilotTokenProvider:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._cached: CopilotAPIToken | None = None

    async def get_api_token(self) -> CopilotAPIToken:
        for env_var in _API_TOKEN_ENV_VARS:
            token = os.environ.get(env_var, "").strip()
            if token:
                return CopilotAPIToken(
                    token=token,
                    expires_at=time.time() + 3600,
                    api_url=get_copilot_api_url(),
                    source=f"env:{env_var}",
                )
        cached = self._cached
        if cached and cached.is_valid:
            return cached
        async with self._lock:
            cached = self._cached
            if cached and cached.is_valid:
                return cached
            for candidate in iter_oauth_token_candidates():
                if _is_copilot_api_token(candidate.token):
                    user_info = _fetch_user_info(candidate.token)
                    api_url = _api_url_from_payload(user_info) or get_copilot_api_url()
                    self._cached = CopilotAPIToken(
                        token=candidate.token,
                        expires_at=time.time() + 1800,
                        api_url=api_url,
                        source=candidate.source,
                    )
                    return self._cached
                try:
                    self._cached = await asyncio.to_thread(_exchange_token_sync, candidate.token)
                    return self._cached
                except Exception as exc:
                    logger.debug("Token candidate from %s failed: %s", candidate.source, exc)
                    continue
            raise RuntimeError(
                "No reusable GitHub Copilot auth token found. Run `copilot` or `gh auth login`, "
                "or set GITHUB_COPILOT_GITHUB_TOKEN."
            )


_provider: CopilotTokenProvider | None = None


def get_copilot_token_provider() -> CopilotTokenProvider:
    global _provider
    if _provider is None:
        _provider = CopilotTokenProvider()
    return _provider


async def get_copilot_api_token() -> CopilotAPIToken:
    return await get_copilot_token_provider().get_api_token()


def get_copilot_token() -> str:
    """Synchronous compatibility helper for older call sites."""

    return asyncio.run(get_copilot_api_token()).token


if __name__ == "__main__":
    async def _main() -> None:
        token = await get_copilot_api_token()
        print(f"Token source: {token.source}")
        print(f"Token kind: {'api' if _is_copilot_api_token(token.token) else 'oauth'}")
        print(f"API URL: {token.api_url}")
        print(f"Expires in: {int(token.expires_at - time.time())}s")

    asyncio.run(_main())
