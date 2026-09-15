"""Tests for the plain SERP-style REST endpoint, `POST|GET /v1/search`.

The endpoint exists because `POST /search` publishes a top-level `oneOf` request
schema, which HTTP-client generators and LLM tool-schema converters flatten to an
empty object (they only read top-level `properties`) and then post `{}`. These
tests pin the properties that make the plain form survive that translation: one
flat object, a top-level `required`, and text-tolerant values for query strings.
"""

import unittest
from unittest.mock import patch

from web_search_cli import openapi, server as server_module

from .test_openapi import _LiveServer

OK_SEARCH = type("Completed", (), {"returncode": 0, "stdout": '{"results": []}', "stderr": ""})


def _forwarded_argv(run_call):
    """The argv the server handed to the CLI, i.e. everything after --config <path>."""
    command = run_call.args[0]
    return command[command.index("--config") + 2:]


class PlainSchemaTests(unittest.TestCase):
    def setUp(self):
        self.spec = openapi.build_openapi_spec(config={})
        self.post = self.spec["paths"][openapi.FLAT_ENDPOINT]["post"]
        self.body = self.post["requestBody"]["content"]["application/json"]["schema"]

    def test_request_schema_is_a_flat_object(self):
        """No top-level oneOf/anyOf/$ref: a client reading only `properties` works."""
        self.assertNotIn("oneOf", self.body)
        self.assertNotIn("anyOf", self.body)
        self.assertNotIn("$ref", self.body)
        self.assertEqual(self.body["type"], "object")
        self.assertEqual(self.body["required"], ["q"])
        self.assertGreater(len(self.body["properties"]), 30)

    def test_serp_aliases_are_published_alongside_canonical_fields(self):
        properties = self.body["properties"]
        for alias, dest in openapi.FLAT_ALIASES.items():
            self.assertIn(alias, properties)
            self.assertIn(dest, properties)
        self.assertEqual(properties["q"]["x-cli-flag"], "--query")
        self.assertEqual(properties["num"]["x-cli-flag"], "--max-results")

    def test_every_advertised_field_is_a_real_cli_flag(self):
        flags = {entry["flag"] for entry in openapi.search_flags()}
        for schema in self.body["properties"].values():
            self.assertIn(schema["x-cli-flag"], flags)

    def test_get_parameters_come_from_the_same_schema(self):
        names = [param["name"] for param in self.spec["paths"][openapi.FLAT_ENDPOINT]["get"]["parameters"]]
        self.assertEqual(names[0], "q")
        for name in names:
            self.assertIn(name, self.body["properties"])

    def test_document_still_validates(self):
        from openapi_spec_validator import validate

        validate(self.spec)


class FlatToArgvTests(unittest.TestCase):
    def test_serp_names_map_to_cli_flags(self):
        argv = openapi.flat_to_argv({"q": "品川 天気", "gl": "jp", "hl": "ja", "num": 5})
        self.assertEqual(argv, ["--country", "jp", "--language", "ja", "--max-results", "5", "--query", "品川 天気"])

    def test_query_string_values_are_coerced_by_declared_type(self):
        argv = openapi.flat_to_argv({
            "q": "x", "num": "3", "compact": "true", "no_cache": "0",
            "include_domains": "a.com,b.com",
        })
        self.assertIn("--max-results", argv)
        self.assertEqual(argv[argv.index("--max-results") + 1], "3")
        self.assertIn("--compact", argv)
        self.assertNotIn("--no-cache", argv)
        self.assertEqual(argv[argv.index("--include-domains") + 1], "a.com")
        self.assertIn("b.com", argv)

    def test_canonical_names_still_work(self):
        self.assertEqual(
            openapi.flat_to_argv({"query": "x", "max_results": 2}),
            openapi.flat_to_argv({"q": "x", "num": 2}),
        )

    def test_alias_conflict_is_rejected(self):
        with self.assertRaises(ValueError) as ctx:
            openapi.flat_to_argv({"q": "a", "query": "b"})
        self.assertIn("disagree", str(ctx.exception))

    def test_query_is_required(self):
        with self.assertRaises(ValueError) as ctx:
            openapi.flat_to_argv({"provider": "exa"})
        self.assertIn('"q"', str(ctx.exception))

    def test_similar_url_alone_is_enough(self):
        self.assertEqual(openapi.flat_to_argv({"similar_url": "https://example.com"}),
                         ["--similar-url", "https://example.com"])

    def test_server_flag_cannot_be_smuggled(self):
        with self.assertRaises(ValueError):
            openapi.flat_to_argv({"q": "x", "searxng_url": "http://evil.example"})
        with self.assertRaises(ValueError):
            openapi.flat_to_argv({"q": "x", "config": "/etc/passwd"})

    def test_unknown_field_is_named(self):
        with self.assertRaises(ValueError) as ctx:
            openapi.flat_to_argv({"q": "x", "api_key": "secret"})
        self.assertIn("api_key", str(ctx.exception))


class PlainEndpointTests(unittest.TestCase):
    def test_post_body_reaches_the_cli(self):
        with _LiveServer() as api, patch.object(server_module.subprocess, "run", return_value=OK_SEARCH) as run:
            status, payload = api.request("POST", "/v1/search", {"q": "hello", "num": 2, "provider": "exa"})
            self.assertEqual(status, 200)
            argv = _forwarded_argv(run.call_args)
            for flag in ("--query", "hello", "--max-results", "2", "--provider", "exa"):
                self.assertIn(flag, argv)

    def test_results_are_numbered(self):
        completed = type("Completed", (), {"returncode": 0, "stdout": '{"results": ['
                                           '{"title": "a", "url": "https://a", "snippet": ""}, '
                                           '{"title": "b", "url": "https://b", "snippet": ""}]}', "stderr": ""})
        with _LiveServer() as api, patch.object(server_module.subprocess, "run", return_value=completed):
            status, payload = api.request("POST", "/v1/search", {"q": "hello"})
            self.assertEqual(status, 200)
            self.assertEqual([item["position"] for item in payload["results"]], [1, 2])

    def test_get_query_string(self):
        with _LiveServer() as api, patch.object(server_module.subprocess, "run", return_value=OK_SEARCH) as run:
            status, _payload = api.request("GET", "/v1/search?q=%E5%93%81%E5%B7%9D%20%E5%A4%A9%E6%B0%97&gl=jp&num=4")
            self.assertEqual(status, 200)
            argv = _forwarded_argv(run.call_args)
            self.assertIn("品川 天気", argv)
            self.assertIn("jp", argv)
            self.assertEqual(argv[argv.index("--max-results") + 1], "4")

    def test_empty_object_is_a_clear_400(self):
        with _LiveServer() as api:
            status, payload = api.request("POST", "/v1/search", {})
            self.assertEqual(status, 400)
            self.assertIn('"q"', payload["error"])

    def test_upstream_failure_is_502_on_the_plain_endpoint_too(self):
        failed = type("Completed", (), {"returncode": 1, "stdout": '{"error": "All providers failed"}', "stderr": "x"})
        with _LiveServer() as api, patch.object(server_module.subprocess, "run", return_value=failed):
            status, payload = api.request("POST", "/v1/search", {"q": "hello"})
            self.assertEqual(status, 502)
            self.assertEqual(payload["error"], "All providers failed")

    def test_x_api_key_header_authenticates(self):
        """The SERP-style header is accepted wherever a bearer token is required."""
        import json
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError

        with _LiveServer() as api, patch.object(server_module.subprocess, "run", return_value=OK_SEARCH):
            for header in ("X-API-KEY", "X-API-Key", "Authorization"):
                value = "test-token" if header != "Authorization" else "Bearer test-token"
                request = Request(api.base_url + "/v1/search", data=json.dumps({"q": "x"}).encode(),
                                  headers={header: value, "Content-Type": "application/json"})
                try:
                    with urlopen(request, timeout=10) as response:
                        status = response.status
                except HTTPError as exc:
                    status = exc.code
                with self.subTest(header=header):
                    self.assertEqual(status, 200)

            wrong = Request(api.base_url + "/v1/search", data=json.dumps({"q": "x"}).encode(),
                            headers={"X-API-KEY": "nope", "Content-Type": "application/json"})
            try:
                urlopen(wrong, timeout=10)
                status = 200
            except HTTPError as exc:
                status = exc.code
            self.assertEqual(status, 401)

    def test_argv_form_is_not_accepted_on_the_plain_endpoint(self):
        with _LiveServer() as api:
            status, payload = api.request("POST", "/v1/search", {"argv": ["--query", "x"]})
            self.assertEqual(status, 400)
            self.assertIn("argv", payload["error"])

    def test_search_endpoint_unchanged(self):
        """The CLI/satellite dialect still works exactly as before."""
        with _LiveServer() as api, patch.object(server_module.subprocess, "run", return_value=OK_SEARCH) as run:
            status, _payload = api.request("POST", "/search", {"argv": ["--query", "x"]})
            self.assertEqual(status, 200)
            self.assertEqual(_forwarded_argv(run.call_args), ["--query", "x"])


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
