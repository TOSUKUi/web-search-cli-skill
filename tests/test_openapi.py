"""Non-network tests for the OpenAPI document published by server mode.

The document is generated from the CLI parser, so these tests assert the
document stays in sync with that parser, that rejected flags are never
published as request fields, and that the named-field request form converts to
the CLI argv the server would run.
"""

import json
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from web_search_cli import openapi, server as server_module
from web_search_cli.search import build_parser


EXPECTED_ENDPOINTS = {"/search", "/health", "/openapi.json"}


def _spec():
    return openapi.build_openapi_spec(config={})


def _fields():
    return _spec()["components"]["schemas"]["SearchFields"]["properties"]


class SpecDocumentTests(unittest.TestCase):
    def setUp(self):
        self.spec = _spec()

    def test_valid_openapi_document_shape(self):
        self.assertEqual(self.spec["openapi"], openapi.OPENAPI_VERSION)
        self.assertTrue(self.spec["info"]["title"])
        self.assertTrue(self.spec["info"]["version"])
        self.assertEqual(set(self.spec["paths"]), EXPECTED_ENDPOINTS)
        self.assertIn("bearerAuth", self.spec["components"]["securitySchemes"])
        for path, operations in self.spec["paths"].items():
            for method, operation in operations.items():
                self.assertTrue(operation["operationId"], f"{method} {path}")
                self.assertTrue(operation["responses"], f"{method} {path}")
                self.assertTrue(operation["description"], f"{method} {path}")

    def test_search_documented_as_post_with_json_body(self):
        operation = self.spec["paths"]["/search"]["post"]
        self.assertEqual(operation["requestBody"]["content"]["application/json"]["schema"]["$ref"],
                         "#/components/schemas/SearchRequest")
        self.assertEqual(
            set(operation["responses"]), {"200", "400", "401", "413", "502", "504"}
        )

    def test_all_component_refs_resolve(self):
        rendered = json.dumps(self.spec)
        for schema_name in ("SearchRequest", "SearchFields", "SearchResult", "ResultItem",
                            "RoutingInfo", "Health", "Error", "SearchUpstreamError"):
            self.assertIn(schema_name, self.spec["components"]["schemas"])
        self.assertIn("#/components/schemas/ResultItem", rendered)

    def test_document_is_json_serializable(self):
        json.dumps(self.spec)

    def test_spec_validates_against_the_openapi_schema(self):
        """Structural check by an external validator when it is installed (dev-only)."""
        try:
            from openapi_spec_validator import validate
        except ImportError:
            self.skipTest("openapi-spec-validator is not installed")
        validate(self.spec)


class SpecDerivedFromParserTests(unittest.TestCase):
    def test_every_cli_flag_is_documented_or_explained(self):
        parser = build_parser({})
        cli_flags = {
            next((s for s in action.option_strings if s.startswith("--")), action.option_strings[0])
            for action in parser._actions
            if action.option_strings
        }
        documented = {schema["x-cli-flag"] for schema in _fields().values()}
        unexposed = {item["flag"] for item in _spec()["x-web-search-plus"]["unexposedFlags"]}
        self.assertEqual(cli_flags, documented | unexposed)
        self.assertFalse(documented & unexposed)

    def test_server_rejected_flags_are_neither_published_as_fields_nor_advertised(self):
        unexposed = _spec()["x-web-search-plus"]["unexposedFlags"]
        documented = {schema["x-cli-flag"] for schema in _fields().values()}
        self.assertFalse(documented & set(server_module.FORBIDDEN_SATELLITE_FLAGS))
        self.assertEqual(
            {item["flag"] for item in unexposed if item["reason"] == "rejected_by_server"},
            set(server_module.FORBIDDEN_SATELLITE_FLAGS),
        )
        self.assertTrue(unexposed)

    def test_field_types_and_enums_follow_the_parser(self):
        fields = _fields()
        self.assertEqual(fields["max_results"]["type"], "integer")
        self.assertEqual(fields["query"]["type"], "string")
        self.assertEqual(fields["provider"]["enum"], openapi.PROVIDERS)
        self.assertEqual(fields["include_domains"]["type"], "array")
        self.assertEqual(fields["include_domains"]["items"]["type"], "string")
        self.assertEqual(fields["images"]["type"], "boolean")
        self.assertIn("hour", fields["time_range"]["enum"])

    def test_credential_bearing_defaults_are_not_published(self):
        for dest in openapi.REDACTED_DEFAULT_DESTS:
            self.assertNotIn("default", _fields().get(dest, {}))

    def test_omitted_flags_carry_a_reason(self):
        for item in _spec()["x-web-search-plus"]["unexposedFlags"]:
            self.assertIn(item["reason"], {"rejected_by_server", "local_only", "maintenance_command"})


class StructuredToArgvTests(unittest.TestCase):
    def test_scalars_flags_and_lists_become_argv(self):
        argv = openapi.structured_to_argv({
            "query": "capital of france",
            "provider": "exa",
            "max_results": 3,
            "images": True,
            "include_domains": ["example.com", "example.org"],
        })
        self.assertEqual(argv, [
            "--images",
            "--include-domains", "example.com", "example.org",
            "--max-results", "3",
            "--provider", "exa",
            "--query", "capital of france",
        ])

    def test_converted_argv_parses_back_to_the_same_values(self):
        payload = {
            "query": "how does https work",
            "provider": "tavily",
            "max_results": 7,
            "depth": "advanced",
            "raw_content": True,
            "exclude_domains": ["spam.example"],
            "no_cache": True,
        }
        parsed = build_parser({}).parse_args(openapi.structured_to_argv(payload))
        for key, value in payload.items():
            self.assertEqual(getattr(parsed, key), value, key)

    def test_false_boolean_is_omitted(self):
        self.assertEqual(
            openapi.structured_to_argv({"query": "x", "compact": False}),
            ["--query", "x"],
        )

    def test_none_values_are_ignored(self):
        self.assertEqual(
            openapi.structured_to_argv({"query": "x", "provider": None, "engines": []}),
            ["--query", "x"],
        )

    def test_aliases_and_short_flags_use_long_form(self):
        argv = openapi.structured_to_argv({"query": "x", "max_results": 2})
        self.assertIn("--max-results", argv)
        self.assertNotIn("-n", argv)

    def test_unknown_field_names_the_field(self):
        with self.assertRaises(ValueError) as ctx:
            openapi.structured_to_argv({"query": "x", "provider_key": "secret"})
        self.assertIn("provider_key", str(ctx.exception))

    def test_enum_member_enforced(self):
        with self.assertRaises(ValueError) as ctx:
            openapi.structured_to_argv({"query": "x", "provider": "not-a-provider"})
        self.assertIn("must be one of", str(ctx.exception))

    def test_numeric_field_must_be_numeric(self):
        with self.assertRaises(ValueError):
            openapi.structured_to_argv({"query": "x", "max_results": "many"})

    def test_boolean_field_must_be_boolean(self):
        with self.assertRaises(ValueError):
            openapi.structured_to_argv({"query": "x", "images": "yes"})

    def test_list_field_must_be_a_list(self):
        with self.assertRaises(ValueError):
            openapi.structured_to_argv({"query": "x", "include_domains": "example.com"})

    def test_rejected_flag_cannot_be_smuggled_as_a_field(self):
        with self.assertRaises(ValueError):
            openapi.structured_to_argv({"query": "x", "searxng_url": "http://evil.example"})

    def test_converted_argv_passes_server_validation(self):
        argv = openapi.structured_to_argv({"query": "x", "provider": "serper"})
        server_module.validate_forwarded_argv(argv)  # must not raise


class _LiveServer:
    """A real loopback server on an ephemeral port, mirroring serve() wiring."""

    def __enter__(self):
        from http.server import ThreadingHTTPServer

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), server_module._Handler)
        self.server.wsp_config_path = Path("config.json")
        self.server.wsp_token = "test-token"
        self.server.wsp_bind_url = "http://127.0.0.1:1"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address[:2]
        self.base_url = f"http://{host}:{port}"
        return self

    def __exit__(self, *exc_info):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def request(self, method, path, body=None, token="test-token"):
        headers = {"Accept": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = Request(self.base_url + path, data=data, headers=headers, method=method)
        try:
            with urlopen(request, timeout=10) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))


class ServerEndpointTests(unittest.TestCase):
    def test_openapi_endpoint_requires_authentication(self):
        with _LiveServer() as api:
            status, payload = api.request("GET", "/openapi.json", token=None)
            self.assertEqual((status, payload), (401, {"error": "Unauthorized"}))

    def test_openapi_endpoint_serves_the_document(self):
        with _LiveServer() as api:
            status, document = api.request("GET", "/openapi.json")
            self.assertEqual(status, 200)
            self.assertEqual(set(document["paths"]), EXPECTED_ENDPOINTS)
            self.assertEqual(document["components"]["schemas"]["SearchFields"]["properties"]
                             ["query"]["x-cli-flag"], "--query")

    def test_documented_fields_reach_the_cli_as_parseable_argv(self):
        """Every advertised field must convert to argv the real CLI parser accepts."""
        completed = type("Completed", (), {"returncode": 0, "stdout": '{"results": []}', "stderr": ""})
        with _LiveServer() as api, patch.object(server_module.subprocess, "run", return_value=completed) as run:
            status, document = api.request("GET", "/openapi.json")
            self.assertEqual(status, 200)
            for name, schema in document["components"]["schemas"]["SearchFields"]["properties"].items():
                with self.subTest(field=name):
                    _code, payload = api.request("POST", "/search", {"query": "x", name: _sample(schema)})
                    self.assertEqual(payload, {"results": []})
                    forwarded = run.call_args.args[0]
                    forwarded = forwarded[forwarded.index("--config") + 2:]
                    try:
                        parsed = build_parser({}).parse_args(forwarded)
                    except SystemExit as exc:
                        self.fail(f"{name}: the CLI rejected the converted argv {forwarded}: {exc}")
                    self.assertIn(schema["x-cli-flag"], forwarded)
                    self.assertEqual(parsed.query, _sample(schema) if name == "query" else "x")

    def test_named_fields_reach_the_cli_as_argv(self):
        completed = type("Completed", (), {"returncode": 0, "stdout": '{"results": []}', "stderr": ""})
        with _LiveServer() as api, patch.object(server_module.subprocess, "run", return_value=completed) as run:
            status, payload = api.request("POST", "/search", {"query": "hello", "provider": "exa", "max_results": 2})
            self.assertEqual(status, 200)
            self.assertEqual(payload, {"results": []})
            argv = run.call_args.args[0]
            self.assertEqual(argv[-6:], ["--max-results", "2", "--provider", "exa", "--query", "hello"])

    def test_argv_form_still_works(self):
        completed = type("Completed", (), {"returncode": 0, "stdout": '{"results": []}', "stderr": ""})
        with _LiveServer() as api, patch.object(server_module.subprocess, "run", return_value=completed) as run:
            status, _payload = api.request("POST", "/search", {"argv": ["--query", "hello", "-n", "2"]})
            self.assertEqual(status, 200)
            self.assertEqual(run.call_args.args[0][-4:], ["--query", "hello", "-n", "2"])

    def test_rejected_flags_return_400(self):
        with _LiveServer() as api:
            status, payload = api.request("POST", "/search", {"argv": ["--config", "/tmp/x.json", "-q", "x"]})
            self.assertEqual(status, 400)
            self.assertIn("not allowed", payload["error"])

    def test_body_without_argv_or_fields_returns_400(self):
        with _LiveServer() as api:
            for body in ({}, [], {"provider": "exa"}):
                status, payload = api.request("POST", "/search", body)
                self.assertEqual(status, 400, body)
                self.assertIn("error", payload)

    def test_central_child_never_becomes_a_satellite_client(self):
        """The server must not let its own .env turn a child search into a satellite."""
        completed = type("Completed", (), {"returncode": 0, "stdout": '{"results": []}', "stderr": ""})
        with _LiveServer() as api, patch.object(server_module.subprocess, "run", return_value=completed) as run:
            api.request("POST", "/search", {"query": "hello"})
            env = run.call_args.kwargs["env"]
            self.assertEqual(env["WSP_SATELLITE_URL"], "")
            self.assertEqual(env["WSP_SATELLITE_TOKEN"], "")

    def test_unknown_path_returns_404(self):
        with _LiveServer() as api:
            self.assertEqual(api.request("GET", "/nope")[0], 404)


def _sample(schema):
    """A schema-valid sample value for one advertised field."""
    if "enum" in schema:
        return schema["enum"][0]
    if schema["type"] == "array":
        return ["example.com"]
    if schema["type"] == "boolean":
        return True
    if schema["type"] == "integer":
        return 2
    if schema["type"] == "number":
        return 1.5
    return "sample"


if __name__ == "__main__":
    unittest.main()
