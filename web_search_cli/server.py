"""Optional central configuration/search server for satellite CLI clients.

The server deliberately uses the existing CLI as the execution boundary. This
keeps provider behavior identical in local and satellite modes while ensuring
that credentials and config stay on the server host.
"""

import hmac
import ipaddress
import json
import os
import subprocess
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


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


def _is_loopback_bind(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def serve(config_path: Path, host: str = "127.0.0.1", port: int = 8765, token: Optional[str] = None) -> None:
    """Run the central server until interrupted."""
    config_path = Path(config_path).expanduser().resolve()
    expected_token = _server_token(token)
    if not expected_token and not _is_loopback_bind(host):
        print(json.dumps({"warning": "WSP_SERVER_TOKEN is not set; the central server has no authentication"}), file=sys.stderr)
    server = ThreadingHTTPServer((host, port), _Handler)
    server.wsp_config_path = config_path  # type: ignore[attr-defined]
    server.wsp_token = expected_token  # type: ignore[attr-defined]
    print(json.dumps({
        "mode": "central",
        "host": host,
        "port": port,
        "config": str(config_path),
        "authentication": bool(expected_token),
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
        received = self.headers.get("Authorization", "")
        if received.startswith("Bearer "):
            received = received[7:]
        return hmac.compare_digest(received, expected)

    def do_GET(self) -> None:
        if not self._authorized():
            _json_response(self, 401, {"error": "Unauthorized"})
            return
        if self.path == "/health":
            _json_response(self, 200, {"ok": True, "mode": "central", "config": str(self.server.wsp_config_path)})  # type: ignore[attr-defined]
            return
        _json_response(self, 404, {"error": "Not found"})

    def do_POST(self) -> None:
        if not self._authorized():
            _json_response(self, 401, {"error": "Unauthorized"})
            return
        if self.path != "/search":
            _json_response(self, 404, {"error": "Not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 256 * 1024:
                _json_response(self, 413, {"error": "Request body is too large"})
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            argv = payload.get("argv")
            if not isinstance(argv, list) or not all(isinstance(item, str) for item in argv):
                raise ValueError("Request must contain an argv array of strings")
            validate_forwarded_argv(argv)
            config_path = Path(self.server.wsp_config_path)  # type: ignore[attr-defined]
            command = [sys.executable, "-m", "web_search_cli.search", "--config", str(config_path), *argv]
            child_env = os.environ.copy()
            child_env.pop("WSP_SATELLITE_URL", None)
            child_env.pop("WSP_SATELLITE_TOKEN", None)
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
            if completed.returncode:
                result.setdefault("central_stderr", completed.stderr[-1000:])
                _json_response(self, 502, result)
            else:
                _json_response(self, 200, result)
        except subprocess.TimeoutExpired:
            _json_response(self, 504, {"error": "Central search timed out"})
        except Exception as exc:
            _json_response(self, 400, {"error": str(exc)})
