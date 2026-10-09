import importlib
import sys
import types
import unittest
from unittest.mock import patch


class PaginationTests(unittest.TestCase):
    def setUp(self):
        # Keep these network-contract tests runnable without the LLM runtime.
        stubs = {"providers.common": types.SimpleNamespace(ExternalPaper=lambda **kwargs: types.SimpleNamespace(**kwargs))}
        try:
            import requests
        except ImportError:
            stubs["requests"] = types.SimpleNamespace(RequestException=RuntimeError, Response=object)
        try:
            import loguru
        except ImportError:
            stubs["loguru"] = types.SimpleNamespace(logger=types.SimpleNamespace(info=lambda *a: None, warning=lambda *a: None))
        with patch.dict(sys.modules, stubs):
            self.provider = importlib.import_module("providers.semantic_scholar")

    def test_follows_token_and_skips_previously_scanned_ranks(self):
        calls = []
        def request(params, headers):
            calls.append(dict(params))
            payload = ({"data": [{"title": "one"}, {"title": "two"}], "token": "next"}
                       if "token" not in params else {"data": [{"title": "three"}, {"title": "four"}]})
            return types.SimpleNamespace(json=lambda: payload)
        with patch.object(self.provider, "request_with_retry", request), patch.object(self.provider.time, "sleep"):
            result = self.provider.search_items({"query": "sputtering"}, {}, count=2, skip=2)
        self.assertEqual([p["title"] for p in result], ["three", "four"])
        self.assertEqual(calls[1]["token"], "next")

    def test_zero_budget_and_repeated_token_are_bounded(self):
        with patch.object(self.provider, "request_with_retry") as request:
            self.assertEqual(self.provider.search_items({}, {}, 0), [])
            request.assert_not_called()
        response = types.SimpleNamespace(json=lambda: {"data": [], "token": "same"})
        with patch.object(self.provider, "request_with_retry", return_value=response) as request, patch.object(self.provider.time, "sleep"):
            self.assertEqual(self.provider.search_items({}, {}, 20), [])
            self.assertEqual(request.call_count, 2)

    def test_classic_minimum_is_five_and_new_search_has_no_citation_gate(self):
        calls = []
        def search(params, headers, count, skip=0):
            calls.append((dict(params), count, skip))
            return []
        with patch.object(self.provider, "search_items", search), patch.object(self.provider.time, "sleep"):
            self.provider.fetch_classic_semantic_scholar_papers('"sputtering"')
            self.provider.fetch_semantic_scholar_papers('"sputtering"')
        self.assertEqual(calls[0][0]["minCitationCount"], "5")
        self.assertEqual(calls[0][1], 200)
        self.assertNotIn("minCitationCount", calls[1][0])
        self.assertEqual(calls[1][1], 20)
