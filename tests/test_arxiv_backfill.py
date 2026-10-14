import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import urlparse, parse_qs
from urllib.error import HTTPError
from unittest.mock import patch

from dedupe import dedupe_papers
from eligibility import filter_candidates, collect_arxiv_backfill
from providers.arxiv_recent import fetch_recent_arxiv_papers, parse_feed, request_feed
from source_quota import select_source_quotas


NOW = datetime(2026, 10, 14, 8, tzinfo=timezone.utc)


def paper(identifier, title="Magnetron sputtering of metal films", source="arXiv", doi="", **kwargs):
    return SimpleNamespace(arxiv_id=identifier, title=title, summary="", source=source, doi=doi, **kwargs)


def factory(**kwargs):
    kwargs["arxiv_id"] = kwargs.pop("paper_id")
    return SimpleNamespace(**kwargs)


def feed(entries, total=None):
    body = ''.join(f'<entry><id>http://arxiv.org/abs/{identifier}</id><title>{title}</title>'
                   f'<summary>Magnetron sputtering of metal films.</summary><published>{published}</published></entry>'
                   for identifier, title, published in entries)
    return (f'<feed xmlns="http://www.w3.org/2005/Atom" xmlns:o="http://a9.com/-/spec/opensearch/1.1/">'
            f'<o:totalResults>{len(entries) if total is None else total}</o:totalResults>{body}</feed>').encode()


class BackfillTests(unittest.TestCase):
    def test_all_identities_deduplicate_and_match_old_histories(self):
        original = paper("2610.12345v1", doi="10.1000/example")
        replacement = paper("2610.12345v2", title="A revised title")
        duplicate_title = paper("s2", source="Semantic Scholar", doi="10.1000/other")
        self.assertEqual(dedupe_papers([original, replacement, duplicate_title]), [original])
        for history in ({"id:2610.12345": {"title": "An older title"}},
                        {"doi:10.1000/old": {"title": original.title}}):
            accepted, audit = filter_candidates([original], history)
            self.assertEqual(accepted, [])
            self.assertEqual(audit["papers"][0]["stage"], "history")

    def test_no_search_when_quota_is_met_or_zero(self):
        def unexpected(**kwargs):
            self.fail("Network search should not run")
        daily = [paper(str(i), title=f"Magnetron sputtering {i}") for i in range(5)]
        self.assertEqual(collect_arxiv_backfill(daily, {}, 5, unexpected), daily)
        self.assertEqual(collect_arxiv_backfill([], {}, 0, unexpected), [])

    def test_progressive_windows_apply_every_gate_and_stop_at_quota(self):
        daily = paper("2610.12345")
        sent = paper("2610.12346", title="Reactive sputtering of chromium")
        irrelevant = paper("2610.12347", title="Fusion in a tokamak")
        recent = paper("2610.12348", title="Atomic layer deposition of oxide films")
        older = paper("2610.12349", title="MBE growth of thin films")
        calls, audits = [], []
        def fetch(**window):
            calls.append(window)
            return [daily, sent, irrelevant, recent] if window['days'] == 7 else [recent, older]
        combined = collect_arxiv_backfill([daily], {"id:2610.12346": {"title": sent.title}}, 3,
                                         fetch, on_audit=lambda days, audit: audits.append(audit))
        self.assertEqual(calls, [{"days": 7, "skip_days": 0}, {"days": 14, "skip_days": 7}])
        self.assertEqual(combined, [daily, recent, older])
        self.assertEqual([r['stage'] for r in audits[0]['papers']], ['deduplication', 'history', 'topic', 'eligible'])
        calls.clear()
        collect_arxiv_backfill([daily], {}, 2, lambda **w: calls.append(w) or [recent])
        self.assertEqual(len(calls), 1)

    def test_failed_recent_search_preserves_daily_and_attempts_older_window(self):
        daily = paper("2610.12345")
        older = paper("2610.12349", title="Atomic layer deposition of oxide films")
        errors = []
        def fetch(**window):
            if window['days'] == 7:
                raise RuntimeError("Service unavailable")
            return [older]
        self.assertEqual(collect_arxiv_backfill([daily], {}, 2, fetch, on_error=lambda *args: errors.append(args)), [daily, older])
        self.assertEqual(len(errors), 1)

    def test_selection_preserves_daily_then_seven_day_before_older_high_scores(self):
        daily = paper("2610.12345", score=1)
        seven = paper("2610.12346", title="Atomic layer deposition of oxides", score=2, arxiv_backfill_days=7)
        older = paper("2610.12347", title="MBE growth of thin films", score=10, arxiv_backfill_days=14)
        selected, a, n, c = select_source_quotas([older, seven, daily], [], arxiv_quota=2, semantic_scholar_quota=5)
        self.assertEqual(selected, [daily, seven])
        self.assertEqual((a, n, c), (2, 0, 0))


class ApiTests(unittest.TestCase):
    def test_date_bounds_use_initial_submission_not_latest_version(self):
        result, total, count = parse_feed(feed([
            ("2610.12345v2", "Related", (NOW - timedelta(days=2)).isoformat()),
            ("2609.12345v3", "Too old", (NOW - timedelta(days=20)).isoformat())]),
            NOW-timedelta(days=7), NOW, factory)
        self.assertEqual([p.arxiv_id for p in result], ["2610.12345"])
        self.assertEqual((total, count), (2, 2))

    def test_pagination_date_query_and_candidate_limit(self):
        urls, errors = [], []
        def fetch(url):
            params = parse_qs(urlparse(url).query)
            urls.append(params)
            offset = int(params['start'][0])
            size = int(params['max_results'][0])
            rows = [(f"2610.{i+10000}", f"Magnetron sputtering {i}", (NOW-timedelta(days=10)).isoformat())
                    for i in range(offset, offset+size)]
            return feed(rows, total=250)
        result = fetch_recent_arxiv_papers(days=14, skip_days=7, now=NOW, max_results_per_topic=150,
                    fetch_feed=fetch, paper_factory=factory, on_error=lambda *args: errors.append(args))
        self.assertEqual(len(result), 450)
        self.assertEqual([int(p['start'][0]) for p in urls], [0, 100, 0, 100, 0, 100])
        self.assertTrue(all('202609300800 TO 202610070800' in p['search_query'][0] for p in urls))
        self.assertEqual(len(errors), 3)

    def test_api_error_and_invalid_window_are_not_silent_empty_successes(self):
        with self.assertRaises(ValueError):
            parse_feed(b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><id>http://arxiv.org/api/errors#bad_query</id><summary>Bad query</summary></entry></feed>', NOW-timedelta(days=7), NOW, factory)
        with self.assertRaises(ValueError):
            fetch_recent_arxiv_papers(days=30)

    def test_partial_source_failure_preserves_other_topic_results(self):
        errors = []
        def fetch(url):
            if 'all%3Asputtering' in url:
                raise RuntimeError('HTTP 503')
            return feed([('2610.12345', 'MBE growth of films', (NOW-timedelta(days=1)).isoformat())])
        results = fetch_recent_arxiv_papers(now=NOW, fetch_feed=fetch, paper_factory=factory,
                    on_error=lambda *args: errors.append(args))
        self.assertEqual(len(results), 2)
        self.assertEqual(len(errors), 1)

    def test_http_retries_are_bounded_and_auth_errors_are_not_retried(self):
        for code, attempts in ((429, 3), (503, 3), (403, 1)):
            with patch('providers.arxiv_recent.urllib.request.urlopen', side_effect=HTTPError('https://example.test', code, 'failure', {}, None)) as request, patch('providers.arxiv_recent.time.sleep'):
                with self.assertRaises(HTTPError):
                    request_feed('https://example.test')
                self.assertEqual(request.call_count, attempts)


if __name__ == '__main__':
    unittest.main()
