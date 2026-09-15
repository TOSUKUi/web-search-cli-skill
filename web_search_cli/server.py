"""Optional central configuration/search server for satellite CLI clients.

The server deliberately uses the existing CLI as the execution boundary. This
keeps provider behavior identical in local and satellite modes while ensuring
that credentials and config stay on the server host.

Search requests run through the CLI either way, in two dialects:

* ``POST /v1/search`` (and ``GET /v1/search``) take a flat SERP-style request —
  the body *is* the parameter object: ``{"q": "...", "gl": "jp", "num": 5}``.
  This is the form HTTP-client generators, LLM tool schemas and `curl` use.
* ``POST /search`` takes the raw CLI form ``{"argv": ["--query", "..."]}`` or the
  named-field form, and is what satellite CLI clients call.

The interface is described by the OpenAPI 3 document served at
`GET /openapi.json` (also printable offline with `web-search-plus --openapi`),
which is generated from the CLI parser itself, so it cannot drift from the flags
the CLI accepts.
"""

import hmac
import ipaddress
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlsplit
from urllib.request import Request, urlopen

try:  # package import
    from .openapi import FLAT_ENDPOINT, build_openapi_spec, flat_to_argv, search_flags, structured_to_argv
except ImportError:  # direct script execution inside the package directory
    from openapi import FLAT_ENDPOINT, build_openapi_spec, flat_to_argv, search_flags, structured_to_argv  # type: ignore[no-redef]


class SatelliteError(RuntimeError):
    """Raised when a satellite request cannot be completed."""


FORBIDDEN_SATELLITE_FLAGS = frozenset({
    "--serve", "--satellite", "--satellite-token", "--config",
    # These flags can redirect a central credential-bearing request.
    "--querit-base-url", "--querit-base-path", "--searxng-url",
})


def validate_forwarded_argv(argv: List[str]) -> None:
    """Reject local/server and credential-routing overrides from satellites."""
    if any(item.split("=", 1)[0] in FORBIDDEN_SATELLITE_FLAGS for item in argv):
        raise ValueError("Satellite/server/config flags are not allowed in a search request")


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: Dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def satellite_request(
    base_url: str,
    argv: List[str],
    token: Optional[str] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Send raw CLI arguments to a central server and return its JSON result."""
    if not base_url.startswith(("http://", "https://")):
        raise SatelliteError("Satellite URL must start with http:// or https://")
    payload = {"argv": argv}
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request(
        base_url.rstrip("/") + "/search",
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else str(exc)
        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            data = {"error": body[:500]}
        raise SatelliteError(json.dumps(data, ensure_ascii=False))
    except (URLError, TimeoutError) as exc:
        raise SatelliteError(f"Could not reach satellite server: {exc}")
    if not isinstance(data, dict):
        raise SatelliteError("Satellite server returned a non-object JSON response")
    return data


def _server_token(cli_token: Optional[str]) -> Optional[str]:
    return cli_token or os.environ.get("WSP_SERVER_TOKEN")


def _bearer_from_headers(headers: Any) -> str:
    """Extract the token from `Authorization: Bearer` or the SERP-style `X-API-KEY`."""
    received = headers.get("Authorization", "") or headers.get("X-API-KEY", "") or headers.get("X-API-Key", "")
    if received.startswith("Bearer "):
        received = received[7:]
    return received.strip()


def _query_payload(query: str) -> Dict[str, Any]:
    """Turn a query string into a flat request payload (repeated keys become lists)."""
    payload: Dict[str, Any] = {}
    for name, value in parse_qsl(query, keep_blank_values=True):
        if name in payload:
            existing = payload[name]
            payload[name] = (existing + [value]) if isinstance(existing, list) else [existing, value]
        else:
            payload[name] = value
    return payload


def _numbered(result: Dict[str, Any]) -> Dict[str, Any]:
    """Add a 1-based `position` to each result, SERP-style. Everything else passes through."""
    results = result.get("results")
    if isinstance(results, list):
        for index, item in enumerate(results, start=1):
            if isinstance(item, dict):
                item.setdefault("position", index)
    return result


def run_search_argv(config_path: Path, argv: List[str]) -> Tuple[int, Dict[str, Any]]:
    """Run one search through the CLI, returning (http_status, response_payload).

    This is the single execution path behind every search endpoint: the server
    always shells out to `python -m web_search_cli.search` with its own config, so
    providers, credentials, cooldowns and cache behave exactly as they do for the
    local CLI and for satellite clients.
    """
    command = [sys.executable, "-m", "web_search_cli.search", "--config", str(config_path), *argv]
    child_env = os.environ.copy()
    # A satellite URL in the server's own .env would otherwise turn the
    # child search back into a satellite client (dotenv does not
    # override process variables, so blank them here).
    child_env["WSP_SATELLITE_URL"] = ""
    child_env["WSP_SATELLITE_TOKEN"] = ""
    package_root = Path(__file__).resolve().parent.parent
    existing_pythonpath = child_env.get("PYTHONPATH")
    child_env["PYTHONPATH"] = str(package_root) + (os.pathsep + existing_pythonpath if existing_pythonpath else "")
    completed = subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=300,
        env=child_env,
        cwd=str(package_root),
    )
    stdout = completed.stdout.strip()
    if stdout:
        try:
            result = json.loads(stdout)
        except json.JSONDecodeError:
            result = {"error": "Central CLI returned invalid JSON", "detail": stdout[-1000:]}
    else:
        result = {"error": "Central CLI returned no JSON", "detail": completed.stderr[-1000:]}
    if not isinstance(result, dict):
        result = {"results": result}
    if completed.returncode:
        result.setdefault("central_stderr", completed.stderr[-1000:])
        return 502, result
    return 200, result


def _is_loopback_bind(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _flag_table(server: Any) -> List[Dict[str, Any]]:
    """Derived flag table, built once per server process."""
    flags = getattr(server, "wsp_flags", None)
    if flags is None:
        flags = search_flags()
        server.wsp_flags = flags
    return flags


def _openapi_document(server: Any) -> Dict[str, Any]:
    """OpenAPI document for this server, built on first request and cached.

    Built from the server's own config so published flag defaults match what the
    server will actually apply.
    """
    document = getattr(server, "wsp_openapi_spec", None)
    if document is None:
        try:
            from .search import load_config
        except ImportError:
            from search import load_config  # type: ignore[no-redef]
        document = build_openapi_spec(
            config=load_config(str(server.wsp_config_path)),
            bind_url=getattr(server, "wsp_bind_url", None),
        )
        server.wsp_openapi_spec = document
    return document


def serve(config_path: Path, host: str = "127.0.0.1", port: int = 8765, token: Optional[str] = None) -> None:
    """Run the central server until interrupted."""
    config_path = Path(config_path).expanduser().resolve()
    expected_token = _server_token(token)
    if not expected_token and not _is_loopback_bind(host):
        print(json.dumps({"warning": "WSP_SERVER_TOKEN is not set; the central server has no authentication"}), file=sys.stderr)
    server = ThreadingHTTPServer((host, port), _Handler)
    server.wsp_config_path = config_path  # type: ignore[attr-defined]
    server.wsp_token = expected_token  # type: ignore[attr-defined]
    server.wsp_bind_url = f"http://{host}:{port}"  # type: ignore[attr-defined]
    print(json.dumps({
        "mode": "central",
        "host": host,
        "port": port,
        "config": str(config_path),
        "authentication": bool(expected_token),
        "endpoints": ["POST /v1/search", "GET /v1/search", "POST /search", "GET /health", "GET /openapi.json"],
    }), flush=True)
    try:
        server.serve_forever()
    finally:
        server.server_close()


class _Handler(BaseHTTPRequestHandler):
    server_version = "web-search-plus-central/1"

    def log_message(self, format: str, *args: Any) -> None:
        # Avoid query strings and request bodies in the server log.
        sys.stderr.write("web-search-plus: " + format % args + "\n")

    def _authorized(self) -> bool:
        expected = getattr(self.server, "wsp_token", None)
        if not expected:
            return True
        return hmac.compare_digest(_bearer_from_headers(self.headers), expected)

    def do_GET(self) -> None:
        if not self._authorized():
            _json_response(self, 401, {"error": "Unauthorized"})
            return
        parts = urlsplit(self.path)
        if parts.path == "/health":
            _json_response(self, 200, {"ok": True, "mode": "central", "config": str(self.server.wsp_config_path)})  # type: ignore[attr-defined]
            return
        if parts.path == "/openapi.json":
            _json_response(self, 200, _openapi_document(self.server))
            return
        if parts.path == FLAT_ENDPOINT:
            try:
                argv = flat_to_argv(_query_payload(parts.query), _flag_table(self.server))
                validate_forwarded_argv(argv)
                status, result = run_search_argv(Path(self.server.wsp_config_path), argv)  # type: ignore[attr-defined]
                _json_response(self, status, _numbered(result))
            except subprocess.TimeoutExpired:
                _json_response(self, 504, {"error": "Central search timed out"})
            except Exception as exc:
                _json_response(self, 400, {"error": str(exc)})
            return
        _json_response(self, 404, {"error": "Not found"})

    def _request_argv(self, payload: Any) -> List[str]:
        """Accept raw CLI argv or named search fields, returning CLI arguments."""
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object")
        argv = payload.get("argv")
        if argv is not None:
            if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
                raise ValueError("Request must contain an argv array of strings")
            return argv
        if payload:
            argv = structured_to_argv(payload, _flag_table(self.server))
            # GET /openapi.json declares query-or-similar_url as required for this
            # form, so reject it here instead of letting the CLI fail as a 502.
            if not {"--query", "-q", "--similar-url"} & set(argv):
                raise ValueError('Named search fields require "query" (or "similar_url")')
            return argv
        raise ValueError('Request must contain an "argv" array or named search fields')

    def _read_json_body(self) -> Any:
        """Read and parse the JSON request body, enforcing the size cap."""
        length = int(self.headers.get("Content-Length", "0"))
        if length > 256 * 1024:
            raise ValueError("Request body is too large")
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_POST(self) -> None:
        if not self._authorized():
            _json_response(self, 401, {"error": "Unauthorized"})
            return
        path = urlsplit(self.path).path.rstrip("/")
        if path not in ("/search", FLAT_ENDPOINT):
            _json_response(self, 404, {"error": "Not found"})
            return
        try:
            payload = self._read_json_body()
            if path == FLAT_ENDPOINT:
                argv = flat_to_argv(payload, _flag_table(self.server))
            else:
                argv = self._request_argv(payload)
            validate_forwarded_argv(argv)
            status, result = run_search_argv(Path(self.server.wsp_config_path), argv)  # type: ignore[attr-defined]
            _json_response(self, status, _numbered(result) if path == FLAT_ENDPOINT else result)
        except subprocess.TimeoutExpired:
            _json_response(self, 504, {"error": "Central search timed out"})
        except ValueError as exc:
            _json_response(self, 413 if "too large" in str(exc) else 400, {"error": str(exc)})
        except Exception as exc:
            _json_response(self, 400, {"error": str(exc)})
