import os
import unittest
from unittest.mock import patch

from web_search_cli import webui


# Keep tests deterministic even when the developer shell has real keys exported.
_REAL_KEYS = {k: os.environ.get(k) for k in (
    "SERPER_API_KEY", "TAVILY_API_KEY", "EXA_API_KEY", "QUERIT_API_KEY",
    "SERPAPI_API_KEY", "SCRAPERAPI_API_KEY", "BRIGHTDATA_API_KEY",
    "BRIGHTDATA_SERP_ZONE", "SEARXNG_INSTANCE_URL", "GOOGLE_CSE_ID",
)}


def _clean_env():
    """Context manager removing real provider credentials from the environment."""
    return patch.dict(os.environ, {k: "" for k in _REAL_KEYS if _REAL_KEYS.get(k)}, clear=False)


class ProviderConfiguredTests(unittest.TestCase):
    def test_serper_configured_from_config(self):
        config = {"serper": {"api_key": "a-valid-key-123"}}
        self.assertTrue(webui.provider_configured("serper", config))
        self.assertEqual(webui.credential_count("serper", config), 1)

    def test_unconfigured_provider(self):
        with _clean_env():
            self.assertFalse(webui.provider_configured("serper", {}))
            self.assertEqual(webui.credential_count("serper", {}), 0)

    def test_multiple_keys_count(self):
        config = {"tavily": {"api_key": ["key-one-abcdef", "key-two-abcdef"]}}
        self.assertEqual(webui.credential_count("tavily", config), 2)

    def test_brightdata_requires_zone(self):
        config = {"brightdata": {"api_key": "brightdata-key-123"}}
        with _clean_env():
            self.assertFalse(webui.provider_configured("brightdata", config))
            os.environ["BRIGHTDATA_SERP_ZONE"] = "serp_zone1"
            self.assertTrue(webui.provider_configured("brightdata", config))

    def test_google_cse_requires_engine_id(self):
        config = {"google_cse": {"api_key": "google-key-123"}}
        with _clean_env():
            self.assertFalse(webui.provider_configured("google_cse", config))
            os.environ["GOOGLE_CSE_ID"] = "engine-id"
            self.assertTrue(webui.provider_configured("google_cse", config))

    def test_searxng_requires_instance_url(self):
        with _clean_env():
            self.assertFalse(webui.provider_configured("searxng", {}))
            os.environ["SEARXNG_INSTANCE_URL"] = "http://127.0.0.1:8888"
            self.assertTrue(webui.provider_configured("searxng", {}))


class QuotaParsingTests(unittest.TestCase):
    @patch.object(webui, "_get_json")
    def test_tavily_quota(self, get_json):
        get_json.return_value = {
            "key": {"usage": 903},
            "account": {"plan_usage": 903, "plan_limit": 1000},
        }
        result = webui._fetch_quota("tavily", {"tavily": {"api_key": "tavily-key-12345"}}, "tavily-key-12345")
        self.assertIsNotNone(result)
        self.assertEqual(result["used"], 903)
        self.assertEqual(result["limit"], 1000)
        self.assertEqual(result["left"], 97)
        self.assertIsNone(result["reset"])
        get_json.assert_called_once()
        headers = get_json.call_args[0][1]
        self.assertEqual(headers["Authorization"], "Bearer tavily-key-12345")

    @patch.object(webui, "_get_json")
    def test_serpapi_quota(self, get_json):
        get_json.return_value = {
            "account_status": "Active",
            "searches_per_month": 250,
            "plan_searches_left": 249,
            "this_month_usage": 1,
            "plan_renewal_date": "2026-08-16",
        }
        result = webui._fetch_quota("serpapi", {"serpapi": {"api_key": "serpapi-key-123"}}, "serpapi-key-123")
        self.assertIsNotNone(result)
        self.assertEqual(result["used"], 1)
        self.assertEqual(result["left"], 249)
        self.assertEqual(result["limit"], 250)
        self.assertEqual(result["reset"], "2026-08-16")

    @patch.object(webui, "_get_json")
    def test_scraperapi_quota(self, get_json):
        get_json.return_value = {"creditsLeft": 4900, "requestLimit": 5000, "nextBillingDate": "2026-09-08T00:00:00.000Z"}
        result = webui._fetch_quota("scraperapi", {"scraperapi": {"api_key": "scraperapi-key"}}, "scraperapi-key")
        self.assertIsNotNone(result)
        self.assertEqual(result["left"], 4900)
        self.assertEqual(result["limit"], 5000)
        self.assertEqual(result["used"], 100)

    @patch.object(webui, "_get_json")
    def test_scraperapi_zero_credits_is_success(self, get_json):
        get_json.return_value = {"creditsLeft": 0, "requestLimit": 1000}
        result = webui._fetch_quota("scraperapi", {"scraperapi": {"api_key": "scraperapi-key"}}, "scraperapi-key")
        self.assertIsNotNone(result)
        self.assertEqual(result["left"], 0)

    @patch.object(webui, "_get_json")
    def test_quota_network_failure_returns_none(self, get_json):
        get_json.return_value = None
        self.assertIsNone(webui._fetch_quota("tavily", {"tavily": {"api_key": "tavily-key-12345"}}, "tavily-key-12345"))
        self.assertIsNone(webui._fetch_quota("serpapi", {"serpapi": {"api_key": "serpapi-key-123"}}, "serpapi-key-123"))
        self.assertIsNone(webui._fetch_quota("scraperapi", {"scraperapi": {"api_key": "scraperapi-key"}}, "scraperapi-key"))

    def test_no_quota_api_providers(self):
        self.assertNotIn("serper", webui.QUOTA_ENDPOINTS)
        self.assertNotIn("exa", webui.QUOTA_ENDPOINTS)
        self.assertNotIn("querit", webui.QUOTA_ENDPOINTS)
        self.assertNotIn("brightdata", webui.QUOTA_ENDPOINTS)

    def test_dig_missing_path(self):
        self.assertIsNone(webui._dig({"a": {"b": 1}}, ["a", "c"]))


class BuildStatusTests(unittest.TestCase):
    def test_build_status_shape(self):
        with patch.object(webui, "_get_json", return_value=None):
            status = webui.build_status({"serper": {"api_key": "serper-key-123456"}})
        self.assertEqual(status["total"], 11)
        self.assertGreaterEqual(status["configured_count"], 1)
        by_id = {p["id"]: p for p in status["providers"]}
        self.assertEqual(by_id["serper"]["configured"], True)
        self.assertFalse(by_id["serper"]["has_quota_api"])
        self.assertEqual(by_id["tavily"]["has_quota_api"], True)
        self.assertIn("dashboard", by_id["serper"])
        self.assertIn("generated_at", status)


if __name__ == "__main__":
    unittest.main()


class UsageLogTests(unittest.TestCase):
    def test_log_and_read_usage(self):
        import tempfile
        from web_search_cli import search
        with tempfile.TemporaryDirectory() as tmp:
            old = search.USAGE_LOG_FILE
            search.USAGE_LOG_FILE = __import__("pathlib").Path(tmp) / "usage.jsonl"
            try:
                search.log_usage_entry({"ts": 100.0, "provider": "exa", "event": "search", "cost_usd": 0.007})
                search.log_usage_entry({"ts": 200.0, "provider": "serper", "event": "search", "cost_usd": None})
                entries = search.read_usage_log()
                self.assertEqual(len(entries), 2)
                self.assertEqual(entries[0]["provider"], "serper")  # newest first
                summary = search.usage_summary()
                self.assertEqual(summary["providers"]["exa"]["count"], 1)
                self.assertEqual(summary["providers"]["exa"]["cost_usd"], 0.007)
                self.assertEqual(summary["providers"]["serper"]["count"], 1)
                # corrupt lines are skipped
                with open(search.USAGE_LOG_FILE, "a", encoding="utf-8") as f:
                    f.write("not-json\n")
                self.assertEqual(len(search.read_usage_log()), 2)
            finally:
                search.USAGE_LOG_FILE = old

    def test_usage_summary_empty(self):
        import tempfile
        from web_search_cli import search
        with tempfile.TemporaryDirectory() as tmp:
            old = search.USAGE_LOG_FILE
            search.USAGE_LOG_FILE = __import__("pathlib").Path(tmp) / "usage.jsonl"
            try:
                self.assertEqual(search.usage_summary()["total_entries"], 0)
            finally:
                search.USAGE_LOG_FILE = old

    def test_capture_response_headers(self):
        from web_search_cli import search
        class FakeHeaders(dict):
            def items(self):
                return self._items
        class FakeResponse:
            def __init__(self, items):
                self.headers = FakeHeaders()
                self.headers._items = items
        resp = FakeResponse([
            ("X-RateLimit-Remaining", "42"),
            ("Content-Type", "application/json"),
            ("X-Quota-Limit", "1000"),
        ])
        captured = search._capture_response_headers(resp)
        self.assertIn("x-ratelimit-remaining", captured)
        self.assertEqual(captured["x-ratelimit-remaining"], "42")
        self.assertIn("x-quota-limit", captured)
        self.assertNotIn("content-type", captured)

    def test_exa_cost_logging(self):
        from web_search_cli import search
        with patch.object(search, "make_request") as mr, \
             patch.object(search, "log_usage_entry") as log:
            mr.return_value = {
                "costDollars": {"total": 0.007, "search": {"neural": 0.007}},
                "results": [{"title": "T", "url": "https://example.com", "text": "x"}],
            }
            search.search_exa("test", "exa-key-123", max_results=1)
            log.assert_called_once()
            entry = log.call_args[0][0]
            self.assertEqual(entry["provider"], "exa")
            self.assertEqual(entry["cost_usd"], 0.007)
