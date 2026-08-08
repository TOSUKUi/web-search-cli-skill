import os
import unittest
from unittest.mock import patch

from web_search_cli import search, server


class ProviderConfigTests(unittest.TestCase):
    def test_comma_separated_provider_keys(self):
        config = {"serper": {"api_key": ["first-key-value", "second-key-value"]}}
        self.assertEqual(search.get_api_keys("serper", config), ["first-key-value", "second-key-value"])
        with patch.dict(os.environ, {"SERPER_API_KEY": "env-one, env-two"}, clear=False):
            self.assertEqual(search.get_api_keys("serper", {}), ["env-one", "env-two"])

    def test_satellite_rejects_endpoint_overrides(self):
        with self.assertRaises(ValueError):
            server.validate_forwarded_argv(["--provider", "querit", "--querit-base-url", "http://untrusted"])
        server.validate_forwarded_argv(["--provider", "serper", "--query", "work"])

    def test_google_cse_requires_search_engine_id(self):
        with patch.dict(os.environ, {"GOOGLE_CSE_API_KEY": "google-key-value", "GOOGLE_CSE_ID": ""}, clear=False):
            with self.assertRaises(search.ProviderConfigError) as raised:
                search.validate_api_key("google_cse", {"google_cse": {}})
        self.assertIn("GOOGLE_CSE_ID", str(raised.exception))

    def test_google_cse_accepts_configured_search_engine_id(self):
        with patch.dict(os.environ, {"GOOGLE_CSE_API_KEY": "google-key-value"}, clear=False):
            self.assertEqual(
                search.validate_api_key("google_cse", {"google_cse": {"cx": "engine-id"}}),
                "google-key-value",
            )

    def test_brightdata_requires_serp_zone(self):
        with patch.dict(os.environ, {"BRIGHTDATA_API_KEY": "brightdata-key-value", "BRIGHTDATA_SERP_ZONE": ""}, clear=False):
            with self.assertRaises(search.ProviderConfigError) as raised:
                search.validate_api_key("brightdata", {"brightdata": {}})
        self.assertIn("BRIGHTDATA_SERP_ZONE", str(raised.exception))


class ProviderParsingTests(unittest.TestCase):
    @patch.object(search, "make_get_request")
    def test_google_cse_maps_items(self, request):
        request.return_value = {
            "items": [{"title": "Example", "link": "https://example.com", "snippet": "A result"}],
            "searchInformation": {"totalResults": "1"},
        }
        result = search.search_google_cse("example", "google-key", "engine-id", max_results=1)
        self.assertEqual(result["results"][0]["title"], "Example")
        self.assertEqual(result["results"][0]["url"], "https://example.com")

    @patch.object(search, "make_get_request")
    def test_serpapi_maps_organic_results(self, request):
        request.return_value = {"organic_results": [{"title": "Example", "link": "https://example.com", "snippet": "A result"}]}
        result = search.search_serpapi("example", "serp-key", max_results=1)
        self.assertEqual(result["provider"], "serpapi")
        self.assertEqual(result["results"][0]["url"], "https://example.com")

    @patch.object(search, "make_get_request")
    def test_scraperapi_accepts_organic_results(self, request):
        request.return_value = {"organic_results": [{"title": "Example", "link": "https://example.com", "snippet": "A result"}]}
        result = search.search_scraperapi("example", "scraper-key", max_results=1)
        self.assertEqual(result["provider"], "scraperapi")
        self.assertEqual(result["results"][0]["url"], "https://example.com")

    @patch.object(search, "make_request")
    def test_brightdata_maps_parsed_json_results(self, request):
        request.return_value = {"organic": [{"title": "Example", "link": "https://example.com", "description": "A result"}]}
        result = search.search_brightdata("example", "brightdata-key", "serp_api1", max_results=1)
        self.assertEqual(result["provider"], "brightdata")
        self.assertEqual(result["results"][0]["url"], "https://example.com")
        request.assert_called_once()


if __name__ == "__main__":
    unittest.main()
