"""Offline contract tests for the standalone Plugin API v2 example."""

from __future__ import annotations

import asyncio
import json
import sys
import tempfile
import unittest
import urllib.error
import zipfile
from pathlib import Path
from unittest.mock import patch

from maintune_plugin_sdk import PluginAPI, PluginContext


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
import anysearch_plugin as plugin  # noqa: E402
from build_mtp import build  # noqa: E402


class FakeResponse:
    def __init__(self, body: object):
        self.body = json.dumps(body).encode("utf-8") if not isinstance(body, bytes) else body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None

    def read(self, size: int) -> bytes:
        return self.body[:size]


class FakeOpener:
    def __init__(self, response: object):
        self.response = response
        self.request = None
        self.timeout = None

    def open(self, request, timeout):
        self.request = request
        self.timeout = timeout
        if isinstance(self.response, Exception):
            raise self.response
        return FakeResponse(self.response)


class AnySearchTests(unittest.TestCase):
    def context(self, **settings):
        return PluginContext(
            plugin_id="official.anysearch",
            plugin_version="0.1.0",
            data_dir=ROOT,
            config={"api_key": "unit-test-only-value", **settings},
        )

    def test_registration_uses_public_sdk_and_recommends_without_enabling(self):
        api = PluginAPI()
        plugin.register(api)
        self.assertEqual(len(api.registrations()), 1)
        tool = api.registrations()[0]
        self.assertEqual((tool["kind"], tool["name"]), ("tool", "search"))
        self.assertEqual(tool["recommended_agents"], ["code_worker"])
        self.assertEqual(tool["input_schema"]["required"], ["query"])
        self.assertEqual(tool["input_schema"]["properties"]["max_results"]["maximum"], 10)

    def test_search_post_bearer_and_result_mapping_without_network(self):
        opener = FakeOpener({
            "code": 0,
            "data": {"results": [
                {"url": "https://example.com/one", "title": "One", "snippet": "First", "content": "not returned"},
                {"url": "https://example.com/one", "title": "Duplicate"},
                {"url": "https://example.com/two", "title": "Two"},
                {"url": "javascript:unsafe", "title": "Unsafe"},
            ]},
        })
        with patch.object(plugin.urllib.request, "build_opener", return_value=opener) as builder:
            result = asyncio.run(plugin.search(self.context(max_results=1, zone="cn", language="zh"), "  Maintune  ", 3))
        self.assertEqual(opener.request.full_url, "https://api.anysearch.com/v1/search")
        self.assertEqual(opener.request.get_method(), "POST")
        self.assertEqual(opener.request.get_header("Authorization"), "Bearer unit-test-only-value")
        self.assertEqual(opener.timeout, 15)
        self.assertIsInstance(builder.call_args.args[0], plugin._NoRedirect)
        self.assertEqual(json.loads(opener.request.data), {
            "query": "Maintune", "max_results": 1, "format": "json", "zone": "cn", "language": "zh",
        })
        self.assertEqual(result, {"sources": [{"url": "https://example.com/one", "title": "One", "snippet": "First"}], "truncated": True})

    def test_credential_and_url_validation_happen_before_http(self):
        with patch.object(plugin.urllib.request, "build_opener") as builder:
            with self.assertRaisesRegex(plugin.AnySearchError, "Configure a valid"):
                asyncio.run(plugin.search(self.context(api_key=""), "topic"))
            for base_url in ("http://example.com", "https://user:pass@example.com", "https://example.com/?q=x"):
                with self.assertRaises(plugin.AnySearchError):
                    asyncio.run(plugin.search(self.context(base_url=base_url), "topic"))
            builder.assert_not_called()

    def test_remote_api_limit_is_enforced_before_http(self):
        with patch.object(plugin.urllib.request, "build_opener") as builder:
            with self.assertRaisesRegex(plugin.AnySearchError, "between 1 and 10"):
                asyncio.run(plugin.search(self.context(), "topic", 11))
            builder.assert_not_called()

    def test_redirect_handler_never_reuses_authorization(self):
        self.assertIsNone(plugin._NoRedirect().redirect_request(None, None, 302, "redirect", {}, "https://other.example/"))

    def test_http_and_application_errors_never_echo_remote_body_or_key(self):
        secret = "unit-test-only-value"
        opener = FakeOpener(urllib.error.HTTPError("https://api.anysearch.com/v1/search", 401, secret, {}, None))
        with patch.object(plugin.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(plugin.AnySearchError) as captured:
                asyncio.run(plugin.search(self.context(), "topic"))
        self.assertIn("HTTP 401", str(captured.exception))
        self.assertNotIn(secret, str(captured.exception))
        opener.response = {"code": 17, "message": f"invalid key: {secret}"}
        with patch.object(plugin.urllib.request, "build_opener", return_value=opener):
            with self.assertRaises(plugin.AnySearchError) as captured:
                asyncio.run(plugin.search(self.context(), "topic"))
        self.assertIn("code 17", str(captured.exception))
        self.assertNotIn(secret, str(captured.exception))

    def test_malformed_and_empty_results(self):
        self.assertEqual(plugin._map_response({"code": 0}, 10), {"sources": [], "truncated": False})
        with self.assertRaises(plugin.AnySearchError):
            plugin._map_response({"code": 0, "data": {"results": "bad"}}, 10)
        with self.assertRaises(plugin.AnySearchError):
            plugin._map_response({"code": "0"}, 10)

    def test_reproducible_mtp_contains_only_declared_files(self):
        with tempfile.TemporaryDirectory() as temp:
            first, second = Path(temp) / "first.mtp", Path(temp) / "second.mtp"
            build(first)
            build(second)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            with zipfile.ZipFile(first) as archive:
                self.assertEqual(set(archive.namelist()), set(("manifest.yaml", "README.md", "CHANGELOG.md", "LICENSE", "requirements.txt", "src/anysearch_plugin.py")))
                manifest = json.loads(archive.read("manifest.yaml"))
            self.assertEqual(manifest["plugin_api"], 2)
            self.assertEqual(manifest["id"], "official.anysearch")
            self.assertEqual(manifest["version"], "0.1.0")
            self.assertEqual(manifest["license"], "AGPL-3.0-only")
            self.assertEqual(manifest["runtime"], {"default": "isolated", "supported": ["isolated"]})
            self.assertTrue(manifest["config_schema"]["properties"]["api_key"]["secret"])


if __name__ == "__main__":
    unittest.main()
