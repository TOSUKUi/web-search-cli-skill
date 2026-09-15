"""OpenAPI 3 description of the search interface exposed by server mode.

``--serve`` executes every search through the CLI itself, so the HTTP surface
*is* the CLI flag surface. To keep the published contract honest, the request
schema here is derived from the live argparse parser
(``web_search_cli.search.build_parser``) instead of a hand-maintained copy: add
a flag to the CLI and it appears in ``GET /openapi.json`` with the same type and
enum constraints, and the same flag can be sent either as CLI ``argv`` or as a
named JSON field.

Documented endpoints:

    POST /search        run one search (argv form or named-field form)
    GET  /health        liveness probe
    GET  /openapi.json  this document

Credential-routing flags are never advertised, because the central server
rejects them (see ``server.FORBIDDEN_SATELLITE_FLAGS``).

Run ``web-search-plus --openapi`` to print this document without starting a
server.
"""

import json
from typing import Any, Dict, List, Optional, Tuple

try:  # package import
    from .search import build_parser
except ImportError:  # direct script execution inside the package directory
    from search import build_parser  # type: ignore[no-redef]

try:
    from . import __version__
except ImportError:  # pragma: no cover - script execution fallback
    __version__ = "0.0.0"


OPENAPI_VERSION = "3.0.3"

# Flags that address the local process or the transport itself. They are never
# part of the HTTP search interface.
LOCAL_ONLY_FLAGS = frozenset({
    "--help",
    "--config",
    "--serve",
    "--server-host",
    "--server-port",
    "--server-token",
    "--satellite",
    "--satellite-token",
    "--satellite-timeout",
    "--openapi",
})

# Maintenance commands. /search does run them (the server shells out to the
# CLI), but they are not part of the documented search interface.
MAINTENANCE_FLAGS = frozenset({"--clear-cache", "--cache-stats"})

# Config-derived defaults that must not be echoed into a public document.
REDACTED_DEFAULT_DESTS = frozenset({"config_path", "google_cse_id"})

PROVIDERS = [
    "serper", "tavily", "querit", "exa", "perplexity", "you",
    "searxng", "google_cse", "serpapi", "scraperapi", "brightdata", "auto",
]


def _forbidden_flags() -> frozenset:
    """Flags the central server rejects, imported lazily to avoid a cycle."""
    try:
        from .server import FORBIDDEN_SATELLITE_FLAGS
    except ImportError:  # pragma: no cover - script execution fallback
        from server import FORBIDDEN_SATELLITE_FLAGS  # type: ignore[no-redef]
    return frozenset(FORBIDDEN_SATELLITE_FLAGS)


def _json_type(action: Any) -> str:
    if isinstance(action.const, bool):
        return "boolean"
    if action.type is int:
        return "integer"
    if action.type is float:
        return "number"
    return "string"


def _flag_schema(action: Any, include_default: bool = True) -> Dict[str, Any]:
    """Map one argparse action onto a JSON Schema fragment."""
    json_type = _json_type(action)
    if action.nargs in ("+", "*", "A..."):
        schema: Dict[str, Any] = {"type": "array", "items": {"type": json_type}}
        if action.choices:
            schema["items"]["enum"] = list(action.choices)
    else:
        schema = {"type": json_type}
        if action.choices:
            schema["enum"] = list(action.choices)
    if json_type == "boolean":
        schema["default"] = bool(action.default)
    elif (
        include_default
        and isinstance(action.default, (str, int, float, bool))
        and action.dest not in REDACTED_DEFAULT_DESTS
    ):
        schema["default"] = action.default
    return schema


def _inventory(source: Any = None) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (search flags, omitted flags) derived from the CLI parser.

    `source` is either an already-built argparse parser or a config dict to
    build one from (so config-derived defaults show up in the document).
    """
    parser = source if hasattr(source, "_actions") else build_parser(source or {})
    forbidden = _forbidden_flags()
    search_flags: List[Dict[str, Any]] = []
    omitted: List[Dict[str, Any]] = []
    for action in parser._actions:
        if not action.option_strings:  # positional argument
            continue
        flag = next((s for s in action.option_strings if s.startswith("--")), action.option_strings[0])
        if flag in forbidden:
            omitted.append({"flag": flag, "reason": "rejected_by_server"})
            continue
        if flag in LOCAL_ONLY_FLAGS:
            omitted.append({"flag": flag, "reason": "local_only"})
            continue
        if flag in MAINTENANCE_FLAGS:
            omitted.append({"flag": flag, "reason": "maintenance_command"})
            continue
        entry = {"flag": flag, "dest": action.dest}
        aliases = [s for s in action.option_strings if s != flag]
        if aliases:
            entry["aliases"] = aliases
        entry.update(_flag_schema(action))
        entry["description"] = action.help or ""
        search_flags.append(entry)
    search_flags.sort(key=lambda item: item["dest"])
    omitted.sort(key=lambda item: item["flag"])
    return search_flags, omitted


def search_flags(config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Flags accepted by ``POST /search`` (also usable as JSON field names)."""
    return _inventory(config)[0]


def omitted_flags(config: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Parser flags that ``POST /search`` does not expose, with the reason."""
    return _inventory(config)[1]


def structured_to_argv(payload: Dict[str, Any], flags: Optional[List[Dict[str, Any]]] = None) -> List[str]:
    """Convert named search fields into CLI arguments.

    This is the counterpart of the ``SearchFields`` schema: the server accepts
    ``{"query": "...", "provider": "exa"}`` and turns it into
    ``["--query", "...", "--provider", "exa"]``. Enum members and value types are
    validated against the same derived flag table, so bad input fails as HTTP 400
    instead of being handed to the CLI.

    Raises:
        ValueError: unknown field, wrong type, or a value outside an enum.
    """
    if not isinstance(payload, dict):
        raise ValueError("Request body must be a JSON object")
    known = flags if flags is not None else search_flags()
    by_dest = {item["dest"]: item for item in known}
    unknown = sorted(name for name in payload if name not in by_dest)
    if unknown:
        raise ValueError(
            "Unknown search field(s): " + ", ".join(unknown)
            + ". Send CLI flags as {\"argv\": [...]}, or see GET /openapi.json."
        )

    argv: List[str] = []
    for spec in known:  # stable order, independent of key order in the payload
        name = spec["dest"]
        if name not in payload or payload[name] is None:
            continue
        value = payload[name]
        flag = spec["flag"]
        kind = spec["type"]
        if kind == "boolean":
            if not isinstance(value, bool):
                raise ValueError(f"{name} must be a boolean")
            if value:
                argv.append(flag)
            continue
        if kind == "array":
            if isinstance(value, str) or not isinstance(value, (list, tuple)):
                raise ValueError(f"{name} must be an array of strings")
            items = [str(item) for item in value]
            if not items:
                continue
            enum = spec.get("items", {}).get("enum")
            _check_enum(name, items, enum)
            argv.append(flag)
            argv.extend(items)
            continue
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ValueError(f"{name} must be {kind}")
        if kind in ("integer", "number"):
            try:
                value = int(value) if kind == "integer" else float(value)
            except (TypeError, ValueError):
                raise ValueError(f"{name} must be {kind}")
        else:
            value = str(value)
        _check_enum(name, [value], spec.get("enum"))
        argv.extend([flag, str(value)])
    return argv


def _check_enum(name: str, values: List[Any], enum: Optional[List[Any]]) -> None:
    if not enum:
        return
    allowed = {str(choice) for choice in enum}
    bad = [value for value in values if str(value) not in allowed]
    if bad:
        raise ValueError(f"{name} must be one of: {', '.join(sorted(allowed))}")


# -----------------------------------------------------------------------------
# Response schemas (provider payloads, not derivable from the parser)
# -----------------------------------------------------------------------------

RESULT_ITEM = {
    "type": "object",
    "description": (
        "One result. Providers fill different subsets; `title`, `url` and "
        "`snippet` are always present."
    ),
    "properties": {
        "title": {"type": "string"},
        "url": {"type": "string"},
        "snippet": {"type": "string"},
        "score": {"type": "number", "description": "Provider relevance score when the provider reports one."},
        "date": {"type": "string", "description": "Publication date when the provider reports one."},
        "published_date": {"type": "string", "nullable": True},
        "author": {"type": "string", "nullable": True},
        "language": {"type": "string"},
        "raw_content": {"type": "string", "description": "Present with `full_page`/`raw_content` requests."},
    },
    "additionalProperties": True,
}

ROUTING_INFO = {
    "type": "object",
    "description": "How the provider was chosen, including auto-routing evidence.",
    "properties": {
        "auto_routed": {"type": "boolean"},
        "provider": {"type": "string", "description": "Provider that actually served the results."},
        "confidence": {"type": "number"},
        "confidence_level": {"type": "string", "enum": ["high", "medium", "low"]},
        "reason": {"type": "string"},
        "top_signals": {
            "type": "array",
            "items": {"type": "object", "properties": {"matched": {"type": "string"}, "weight": {"type": "number"}}},
        },
        "scores": {"type": "object", "additionalProperties": {"type": "number"}},
        "fallback_used": {"type": "boolean"},
        "original_provider": {"type": "string"},
        "fallback_errors": {"type": "array", "items": {"type": "object"}},
        "cooldown_skips": {"type": "array", "items": {"type": "object"}},
    },
    "additionalProperties": True,
}

SEARCH_RESPONSE = {
    "type": "object",
    "title": "SearchResult",
    "description": (
        "The search payload returned by the central CLI. Extra keys are provider-specific "
        "(for example `knowledge_graph` from Serper or `cost_usd` from Exa). A request with "
        "`explain_routing` returns the routing analysis object instead of search results."
    ),
    "required": ["provider", "query", "results"],
    "properties": {
        "provider": {"type": "string", "enum": PROVIDERS},
        "query": {"type": "string"},
        "results": {"type": "array", "items": {"$ref": "#/components/schemas/ResultItem"}},
        "answer": {"type": "string", "description": "Synthesized or extracted answer when the provider gives one."},
        "images": {"type": "array", "items": {"type": "string"}, "description": "Image URLs when images were requested."},
        "related_searches": {"type": "array", "items": {"type": "string"}},
        "knowledge_graph": {"type": "object", "nullable": True, "additionalProperties": True},
        "metadata": {"type": "object", "additionalProperties": True, "description": "Provider metadata plus dedup/bookkeeping fields."},
        "cost_usd": {"type": "number", "description": "Reported cost (Exa deep modes)."},
        "routing": {"$ref": "#/components/schemas/RoutingInfo"},
        "cached": {"type": "boolean"},
        "cache_age_seconds": {"type": "integer"},
        "deduplicated": {"type": "boolean"},
    },
    "additionalProperties": True,
}

HEALTH_RESPONSE = {
    "type": "object",
    "required": ["ok", "mode"],
    "properties": {
        "ok": {"type": "boolean"},
        "mode": {"type": "string", "enum": ["central"]},
        "config": {"type": "string", "description": "Path of the config file this server reads."},
    },
}

ERROR_RESPONSE = {
    "type": "object",
    "title": "Error",
    "description": "Every failure is reported as a JSON object with an `error` message.",
    "required": ["error"],
    "properties": {
        "error": {"type": "string"},
        "detail": {"type": "string", "description": "Truncated CLI output when the failure came from the search core."},
        "central_stderr": {"type": "string", "description": "Truncated CLI stderr for a non-zero exit."},
    },
    "additionalProperties": True,
}

SEARCH_UPSTREAM_ERROR = {
    "type": "object",
    "title": "SearchUpstreamError",
    "description": (
        "The central server could not produce results: every provider failed, or the "
        "search core exited non-zero (unknown flag, missing provider credential, provider outage)."
    ),
    "required": ["error"],
    "properties": {
        "error": {"type": "string"},
        "provider": {"type": "string"},
        "query": {"type": "string"},
        "routing": {"$ref": "#/components/schemas/RoutingInfo"},
        "provider_errors": {"type": "array", "items": {"type": "object"}},
        "cooldown_skips": {"type": "array", "items": {"type": "object"}},
        "detail": {"type": "string"},
        "central_stderr": {"type": "string"},
    },
    "additionalProperties": True,
}


def _unauthorized() -> Dict[str, Any]:
    return {
        "description": "Missing or wrong bearer token. Only returned when the server was started with a token.",
        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
    }


def _fields_schema(flags: List[Dict[str, Any]]) -> Dict[str, Any]:
    """`SearchFields`: named JSON fields mirroring the accepted CLI flags."""
    properties: Dict[str, Any] = {}
    for spec in flags:
        schema = {k: v for k, v in spec.items() if k not in ("flag", "dest", "aliases")}
        schema["x-cli-flag"] = spec["flag"]
        if spec.get("aliases"):
            schema["x-cli-aliases"] = spec["aliases"]
        properties[spec["dest"]] = schema
    return {
        "type": "object",
        "title": "SearchFields",
        "description": (
            "Named search fields; each one mirrors a CLI flag. `query` is required "
            "unless `similar_url` is set. Boolean fields add a flag when true and "
            "nothing when false."
        ),
        "properties": properties,
        "additionalProperties": False,
        "anyOf": [{"required": ["query"]}, {"required": ["similar_url"]}],
    }


def _argv_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "title": "SearchArgv",
        "description": (
            "Raw CLI arguments, exactly as `web-search-plus` would receive them. "
            "Server, satellite and credential-routing flags are rejected."
        ),
        "properties": {
            "argv": {
                "type": "array",
                "minItems": 1,
                "items": {"type": "string"},
                "description": "One CLI token per array item, so `--include-domains a.com b.com` becomes three items.",
                "example": ["--provider", "auto", "--query", "latest AI news", "--compact"],
            }
        },
        "required": ["argv"],
        "additionalProperties": False,
    }


def build_openapi_spec(
    parser: Any = None,
    config: Optional[Dict[str, Any]] = None,
    bind_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the OpenAPI document.

    Args:
        parser: an argparse parser to describe; defaults to one built from `config`.
        config: server configuration used to reflect configured flag defaults.
        bind_url: the address the server is bound to, published as an example server.
    """
    if parser is not None:
        flags, omitted = _inventory(parser)
    else:
        flags, omitted = _inventory(config)

    servers = [{"url": "/", "description": "This server, as requested (behind any TLS/reverse proxy)."}]
    if bind_url:
        servers.append({"url": bind_url, "description": "Address the server process is bound to."})

    search_request = {
        "title": "SearchRequest",
        "description": "Send either raw CLI `argv` or named search fields, never both.",
        "oneOf": [_argv_schema(), {"$ref": "#/components/schemas/SearchFields"}],
    }

    return {
        "openapi": OPENAPI_VERSION,
        "info": {
            "title": "web-search-plus central search server",
            "version": __version__,
            "description": (
                "HTTP front end for the `web-search-plus` search core. The server owns provider "
                "credentials and configuration; clients send search requests only. Requests are "
                "either raw CLI arguments (`argv`) or named fields mirroring the same flags, so "
                "behaviour is identical to running the CLI on the server host.\n\n"
                "Authentication: when the server is started with `--server-token` (or "
                "`WSP_SERVER_TOKEN`), every endpoint requires `Authorization: Bearer <token>`. "
                "An unauthenticated server accepts anonymous requests and must stay on a trusted "
                "network; the server speaks plain HTTP, so terminate TLS in front of it."
            ),
        },
        "servers": servers,
        "security": [{"bearerAuth": []}],
        "tags": [
            {"name": "search", "description": "Multi-provider web search with automatic fallback."},
            {"name": "meta", "description": "Liveness and interface description."},
        ],
        "paths": {
            "/search": {
                "post": {
                    "tags": ["search"],
                    "operationId": "search",
                    "summary": "Run one search on the central server",
                    "description": (
                        "Executes the search core with the supplied arguments, applying the server's "
                        "own configuration, provider credentials, provider cooldowns and cache.\n\n"
                        "Providers tried: `" + "`, `".join(PROVIDERS[:-1]) + "`, or `auto` for "
                        "intent-based routing. If the chosen provider fails or returns too few "
                        "results, configured providers are tried in the server's priority order; the "
                        "response `routing` object reports any fallback.\n\n"
                        "Rejected flags: `" + "`, `".join(sorted(item["flag"] for item in omitted if item["reason"] == "rejected_by_server")) + "` "
                        "(they would redirect a credential-bearing request); they produce HTTP 400.\n\n"
                        "Maintenance flags `--clear-cache` and `--cache-stats` are accepted as argv "
                        "and return cache bookkeeping instead of results. The named-field form requires "
                        "`query` (or `similar_url`)."
                    ),
                    "requestBody": {
                        "required": True,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/SearchRequest"}}},
                    },
                    "responses": {
                        "200": {
                            "description": "Search results from the first provider that satisfied the request.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/SearchResult"}}},
                        },
                        "400": {"$ref": "#/components/responses/MalformedRequest"},
                        "401": _unauthorized(),
                        "413": {
                            "description": "Request body larger than the server's 256 KiB limit.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
                        },
                        "502": {
                            "description": "All providers failed, or the search core exited non-zero.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/SearchUpstreamError"}}},
                        },
                        "504": {
                            "description": "Search exceeded the server's 300 s execution timeout.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
                        },
                    },
                }
            },
            "/health": {
                "get": {
                    "tags": ["meta"],
                    "operationId": "health",
                    "summary": "Liveness probe",
                    "description": "Reports that the server is up and which config file it reads. Used by the Docker healthcheck.",
                    "responses": {
                        "200": {
                            "description": "Server is running.",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Health"}}},
                        },
                        "401": _unauthorized(),
                    },
                }
            },
            "/openapi.json": {
                "get": {
                    "tags": ["meta"],
                    "operationId": "openapi",
                    "summary": "This OpenAPI document",
                    "description": (
                        "The document is generated from the installed CLI parser, so the accepted "
                        "flags, types and enum members match this server build. Authenticated like "
                        "every other endpoint, because flag defaults come from server config."
                    ),
                    "responses": {
                        "200": {
                            "description": "This document.",
                            "content": {"application/json": {"schema": {"type": "object", "additionalProperties": True}}},
                        },
                        "401": _unauthorized(),
                    },
                }
            },
        },
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "description": (
                        "Value of `WSP_SERVER_TOKEN`/`--server-token`. Optional: an unset token "
                        "means the server is deliberately unauthenticated."
                    ),
                }
            },
            "schemas": {
                "SearchRequest": search_request,
                "SearchArgv": _argv_schema(),
                "SearchFields": _fields_schema(flags),
                "SearchResult": SEARCH_RESPONSE,
                "ResultItem": RESULT_ITEM,
                "RoutingInfo": ROUTING_INFO,
                "Health": HEALTH_RESPONSE,
                "Error": ERROR_RESPONSE,
                "SearchUpstreamError": SEARCH_UPSTREAM_ERROR,
            },
            "responses": {
                "MalformedRequest": {
                    "description": (
                        "Body is not JSON, has no `argv` and no known fields, omits `query`/`similar_url` "
                        "in the named-field form, uses an unknown field, violates an enum, or uses a "
                        "rejected flag."
                    ),
                    "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Error"}}},
                }
            },
        },
        "x-web-search-plus": {
            "cli": "web-search-plus",
            "searchFields": {spec["dest"]: spec["flag"] for spec in flags},
            "unexposedFlags": omitted,
            "limits": {"maxRequestBodyBytes": 262144, "searchTimeoutSeconds": 300},
            "authentication": "bearer",
        },
    }


if __name__ == "__main__":  # pragma: no cover - convenience for `python -m web_search_cli.openapi`
    print(json.dumps(build_openapi_spec(), indent=2, ensure_ascii=False))
