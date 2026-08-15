#!/usr/bin/env python3
"""Web UI for checking provider API-key status and remaining quota.

Runs a stdlib-only HTTP server. The page reads credentials through the same
load_config()/get_api_keys()/get_provider_config() code path as the CLI, and
queries each provider's official usage endpoint when one exists. The page and
endpoints only expose presence/counts — never credential values.

Providers without a public usage endpoint report "configured" only, with a
link to the official dashboard.

Run with:

    python -m web_search_cli.webui [--port 8901] [--open]

Endpoints:

    GET /                 the dashboard page
    GET /api/status       provider credential presence + remaining-quota JSON
    GET /health           liveness probe
"""

import argparse
import json
import os
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from .search import (
    _load_env_file,
    get_api_key,
    get_api_keys,
    get_brightdata_zone,
    get_provider_config,
    get_searxng_instance_url,
    load_config,
    usage_summary,
)

# Provider -> usage endpoint description. Each entry knows how to authenticate
# and which response fields carry the quota. providers with no entry have no
# public remaining-quota API (dashboard only).
QUOTA_ENDPOINTS: Dict[str, Dict[str, Any]] = {
    "tavily": {
        "url": "https://api.tavily.com/usage",
        "auth": "bearer",
        "used": ["account", "plan_usage"],
        "limit": ["account", "plan_limit"],
        "dashboard": "https://app.tavily.com/home",
    },
    "serpapi": {
        "url": "https://serpapi.com/account.json",
        "auth": "query",
        "param": "api_key",
        "used": ["this_month_usage"],
        "left": ["plan_searches_left"],
        "limit": ["searches_per_month"],
        "reset": ["plan_renewal_date"],
        "dashboard": "https://serpapi.com/dashboard",
    },
    "scraperapi": {
        "url": "https://api.scraperapi.com/account",
        "auth": "query",
        "param": "api_key",
        "left": ["creditsLeft"],
        "limit": ["requestLimit"],
        "reset": ["nextBillingDate"],
        "dashboard": "https://www.scraperapi.com/dashboard",
    },
}

# Provider display names and dashboard links (used for all providers).
PROVIDER_INFO: Dict[str, Dict[str, str]] = {
    "serper": {"name": "Serper", "dashboard": "https://serper.dev/dashboard"},
    "tavily": {"name": "Tavily", "dashboard": "https://app.tavily.com/home"},
    "querit": {"name": "Querit", "dashboard": "https://querit.ai/dashboard"},
    "exa": {"name": "Exa", "dashboard": "https://dashboard.exa.ai/usage"},
    "perplexity": {"name": "Perplexity (Kilo)", "dashboard": "https://api.kilo.ai/"},
    "you": {"name": "You.com", "dashboard": "https://you.com/api/"},
    "searxng": {"name": "SearXNG", "dashboard": None},
    "google_cse": {"name": "Google CSE", "dashboard": "https://console.cloud.google.com/apis/dashboard"},
    "serpapi": {"name": "SerpApi", "dashboard": "https://serpapi.com/dashboard"},
    "scraperapi": {"name": "ScraperAPI", "dashboard": "https://www.scraperapi.com/dashboard"},
    "brightdata": {"name": "Bright Data", "dashboard": "https://brightdata.com/"},
}

# Providers this CLI can actually search with.
ALL_PROVIDERS = [
    "serper", "tavily", "querit", "exa", "perplexity", "you", "searxng",
    "google_cse", "serpapi", "scraperapi", "brightdata",
]

HTTP_TIMEOUT = 12


# =============================================================================
# Credential resolution (mirrors the CLI's rules)
# =============================================================================

def _searxng_configured(config: Dict[str, Any]) -> bool:
    return bool(get_searxng_instance_url(config))


def provider_configured(provider: str, config: Dict[str, Any]) -> bool:
    """True when the provider has at least one usable credential configured."""
    if provider == "searxng":
        try:
            return _searxng_configured(config)
        except Exception:
            # URL validation may reject the configured instance (e.g. private
            # IP without SEARXNG_ALLOW_PRIVATE) — treat as not usable.
            return False
    if provider == "brightdata":
        # Needs both an API key and a SERP zone.
        if not get_api_key(provider, config):
            return False
        return bool(get_brightdata_zone(config))
    if provider == "google_cse":
        # Needs both an API key and a Programmable Search Engine ID.
        if not get_api_key(provider, config):
            return False
        return bool((get_provider_config(provider, config) or {}).get("cx") or os.environ.get("GOOGLE_CSE_ID"))
    return bool(get_api_key(provider, config))


def credential_count(provider: str, config: Dict[str, Any]) -> int:
    """Number of configured credentials (API keys, or instance URL for SearXNG)."""
    if provider == "searxng":
        return 1 if _searxng_configured(config) else 0
    return len(get_api_keys(provider, config))


# =============================================================================
# Quota lookups
# =============================================================================

def _get_json(url: str, headers: Optional[Dict[str, str]] = None) -> Optional[Any]:
    """GET a URL and parse JSON; return None on any failure."""
    request = Request(url, headers=dict(headers or {}), method="GET")
    try:
        with urlopen(request, timeout=HTTP_TIMEOUT) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def _dig(data: Any, path: List[str]) -> Optional[Any]:
    """Traverse nested dicts/lists by key path; return None on any miss."""
    if not path:
        return None
    for key in path:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def _fetch_quota(
    provider: str, config: Dict[str, Any], key: Optional[str]
) -> Optional[Dict[str, Any]]:
    """Query one provider's usage endpoint; None if unavailable/failed."""
    spec = QUOTA_ENDPOINTS.get(provider)
    if not spec or not key:
        return None
    if provider == "serpapi":
        if len(key) < 10:
            return None
        url = spec["url"] + "?" + urlencode({"api_key": key})
        data = _get_json(url)
        if not isinstance(data, dict):
            return None
        if data.get("account_status") not in (None, "Active"):
            return None
    elif provider == "scraperapi":
        if len(key) < 10:
            return None
        url = spec["url"] + "?" + urlencode({"api_key": key})
        data = _get_json(url)
        if not isinstance(data, dict):
            return None
        # "No credits left" is a valid, useful answer — treat as success.
        if "creditsLeft" not in data and "requestLimit" not in data:
            return None
    elif provider == "tavily":
        url = spec["url"]
        data = _get_json(url, {"Authorization": f"Bearer {key}"})
        if not isinstance(data, dict) or not isinstance(data.get("account"), dict):
            return None
    else:
        return None

    used = _dig(data, spec.get("used", []))
    left = _dig(data, spec.get("left", []))
    limit = _dig(data, spec.get("limit", []))
    reset = _dig(data, spec.get("reset", []))
    used = float(used) if isinstance(used, (int, float)) else None
    left = float(left) if isinstance(left, (int, float)) else None
    limit = float(limit) if isinstance(limit, (int, float)) else None
    if used is None and left is None:
        return None
    if used is None and left is not None and limit is not None:
        used = limit - left
    if left is None and used is not None and limit is not None:
        left = limit - used
    return {
        "used": used,
        "left": left,
        "limit": limit,
        "reset": str(reset) if reset else None,
        "fetched_at": time.time(),
    }


# =============================================================================
# Status assembly
# =============================================================================

def build_status(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Assemble the provider status list (credentials + quota where available)."""
    config = config if config is not None else load_config()
    providers: List[Dict[str, Any]] = []
    for provider in ALL_PROVIDERS:
        info = PROVIDER_INFO.get(provider, {"name": provider, "dashboard": None})
        configured = provider_configured(provider, config)
        keys = credential_count(provider, config)
        quota: Optional[Dict[str, Any]] = None
        if configured and provider in QUOTA_ENDPOINTS:
            quota = _fetch_quota(provider, config, get_api_key(provider, config))
        providers.append({
            "id": provider,
            "name": info["name"],
            "configured": configured,
            "key_count": keys,
            "quota": quota,
            "has_quota_api": provider in QUOTA_ENDPOINTS,
            "dashboard": info.get("dashboard"),
        })
    return {
        "providers": providers,
        "configured_count": sum(1 for p in providers if p["configured"]),
        "total": len(providers),
        "usage": usage_summary(),
        "generated_at": time.time(),
    }


# =============================================================================
# HTTP server
# =============================================================================

PAGE_HTML = None


def _load_page() -> str:
    global PAGE_HTML
    if PAGE_HTML is None:
        path = Path(__file__).resolve().parent / "templates" / "webui.html"
        PAGE_HTML = path.read_text(encoding="utf-8")
    return PAGE_HTML


class _Handler(BaseHTTPRequestHandler):
    server_version = "web-search-plus-webui/1"

    def log_message(self, format: str, *args: Any) -> None:
        # Keep the console quiet: no per-request noise.
        pass

    def _send_json(self, payload: Dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/" or parsed.path == "/index.html":
            page = _load_page()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(page.encode("utf-8"))))
            self.end_headers()
            self.wfile.write(page.encode("utf-8"))
            return
        if parsed.path == "/api/status":
            self._send_json(build_status())
            return
        if parsed.path == "/health":
            self._send_json({"ok": True})
            return
        self._send_json({"error": "Not found"}, status=404)

    do_POST = do_GET  # tolerate POST /api/status for fetch-based tooling


def serve(host: str = "127.0.0.1", port: int = 8901, open_browser: bool = False) -> None:
    """Run the dashboard until interrupted."""
    _load_env_file()
    server = ThreadingHTTPServer((host, port), _Handler)
    if open_browser:
        url = f"http://{host}:{port}/"
        threading.Timer(0.5, lambda: webbrowser.open(url)).start()
    print(json.dumps({
        "mode": "webui",
        "url": f"http://{host}:{port}/",
        "host": host,
        "port": port,
    }, ensure_ascii=False), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Web UI for checking web-search provider quota remaining",
    )
    parser.add_argument("--host", default=os.environ.get("WSP_WEBUI_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("WSP_WEBUI_PORT", "8901")))
    parser.add_argument("--open", action="store_true", help="Open the dashboard in the default browser")
    args = parser.parse_args()
    try:
        serve(host=args.host, port=args.port, open_browser=args.open)
    except OSError as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        sys.exit(2)


if __name__ == "__main__":
    main()
