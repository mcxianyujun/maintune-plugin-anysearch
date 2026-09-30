"""AnySearch Agent Tool using only the public Maintune Plugin API v2 SDK."""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlsplit

from maintune_plugin_sdk import PluginAPI, PluginContext


_DEFAULT_BASE_URL = "https://api.anysearch.com"
_MAX_RESPONSE_BYTES = 1024 * 1024
_TIMEOUT_SECONDS = 15


class AnySearchError(RuntimeError):
    """A safe, credential-free search error for the calling Agent."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):  # noqa: ANN001
        # Never forward Authorization to a redirect target.
        return None


def _endpoint(base_url: str) -> str:
    normalized = base_url.strip()
    if any(ord(character) < 32 for character in normalized):
        raise AnySearchError("AnySearch base URL contains invalid characters")
    try:
        parsed = urlsplit(normalized)
        hostname = parsed.hostname
        username = parsed.username
        password = parsed.password
        _ = parsed.port
    except ValueError:
        raise AnySearchError("AnySearch base URL is invalid") from None
    if (
        parsed.scheme != "https"
        or not hostname
        or username is not None
        or password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise AnySearchError("AnySearch base URL must be an HTTPS URL without credentials or query")
    return normalized.rstrip("/") + "/v1/search"


def _max_results(requested: int, configured: Any) -> int:
    if type(requested) is not int or not 1 <= requested <= 10:
        raise AnySearchError("max_results must be between 1 and 10")
    if type(configured) is not int or not 1 <= configured <= 10:
        raise AnySearchError("Configured max_results must be between 1 and 10")
    return min(requested, configured)


def _map_response(parsed: Any, limit: int) -> dict[str, Any]:
    if not isinstance(parsed, dict):
        raise AnySearchError("AnySearch returned an unexpected response body")
    code = parsed.get("code", 0)
    if type(code) is not int:
        raise AnySearchError("AnySearch returned an unexpected status code")
    if code != 0:
        # Remote error strings can echo request details or credentials.
        raise AnySearchError(f"AnySearch API rejected the search (code {code})")
    data = parsed.get("data")
    if data is not None and not isinstance(data, dict):
        raise AnySearchError("AnySearch returned an unexpected data shape")
    results = data.get("results") if isinstance(data, dict) else None
    if results is None:
        results = []
    if not isinstance(results, list):
        raise AnySearchError("AnySearch returned an unexpected results shape")
    seen: set[str] = set()
    sources: list[dict[str, str]] = []
    for item in results:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not isinstance(url, str) or url in seen or any(ord(character) < 32 for character in url):
            continue
        try:
            source_url = urlsplit(url)
            valid_source = source_url.scheme in ("https", "http") and bool(source_url.hostname)
        except ValueError:
            valid_source = False
        if not valid_source:
            continue
        seen.add(url)
        source = {"url": url}
        for key in ("title", "snippet"):
            value = item.get(key)
            if isinstance(value, str) and value:
                source[key] = value
        sources.append(source)
    return {"sources": sources[:limit], "truncated": len(sources) > limit}


def _http_search(endpoint: str, api_key: str, body: dict[str, Any]) -> Any:
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "maintune-plugin-anysearch/0.1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.build_opener(_NoRedirect()).open(request, timeout=_TIMEOUT_SECONDS) as response:
            payload = response.read(_MAX_RESPONSE_BYTES + 1)
    except urllib.error.HTTPError as error:
        if error.code in (401, 403):
            raise AnySearchError(f"AnySearch authentication failed (HTTP {error.code})") from None
        if error.code == 429:
            raise AnySearchError("AnySearch rate limit reached (HTTP 429)") from None
        raise AnySearchError(f"AnySearch request failed (HTTP {error.code})") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise AnySearchError("AnySearch request failed; check endpoint and network connection") from None
    if len(payload) > _MAX_RESPONSE_BYTES:
        raise AnySearchError("AnySearch response exceeded the size limit")
    try:
        return json.loads(payload)
    except (UnicodeError, json.JSONDecodeError):
        raise AnySearchError("AnySearch returned invalid JSON") from None


async def search(context: PluginContext, query: str, max_results: int = 10) -> dict[str, Any]:
    """Search the public web and return citable URL/title/snippet objects."""
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 500:
        raise AnySearchError("Search query must contain 1 to 500 characters")
    config = context.config
    api_key = config.get("api_key")
    if not isinstance(api_key, str) or not api_key or any(ord(c) < 32 for c in api_key):
        raise AnySearchError("Configure a valid AnySearch API key before searching")
    endpoint = _endpoint(str(config.get("base_url", _DEFAULT_BASE_URL)))
    limit = _max_results(max_results, config.get("max_results", 10))
    body: dict[str, Any] = {"query": query.strip(), "max_results": limit, "format": "json"}
    zone = config.get("zone", "intl")
    if zone not in ("cn", "intl"):
        raise AnySearchError("Configured search region is invalid")
    body["zone"] = zone
    language = config.get("language", "")
    if language:
        if not isinstance(language, str) or len(language) > 32:
            raise AnySearchError("Configured result language is invalid")
        body["language"] = language
    response = await asyncio.to_thread(_http_search, endpoint, api_key, body)
    return _map_response(response, limit)


def register(api: PluginAPI) -> None:
    api.register_tool(
        "search",
        search,
        description="Search the public web with AnySearch. Returns citeable source URLs, titles and snippets.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "minLength": 1, "maxLength": 500},
                "max_results": {"type": "integer", "minimum": 1, "maximum": 10, "default": 10},
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        recommended_agents=["code_worker"],
    )
