from __future__ import annotations

import json
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import date
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from collect_metrics import (  # noqa: E402
    CollectionError,
    GitHub,
    fetch_activity,
    is_meaningful_commit,
    local_day,
    main,
    verified_evidence,
    within,
)
from render_metrics import readme_block, work_trail_svg  # noqa: E402


class FakeGitHub:
    def __init__(self) -> None:
        self.prs = {
            1: {
                "user": {"login": "Rainnnee"},
                "merged_at": "2026-10-13T09:00:00Z",
            },
            2: {"user": {"login": "Rainnnee"}, "merged_at": None},
            3: {
                "user": {"login": "teammate"},
                "merged_at": "2026-10-12T08:30:00Z",
            },
        }
        self.reviews = {
            1: [
                {"state": "APPROVED", "user": {"login": "teammate"}, "submitted_at": "2026-10-13T08:00:00Z"},
                {"state": "APPROVED", "user": {"login": "Rainnnee"}, "submitted_at": "2026-10-13T08:30:00Z"},
                {"state": "COMMENTED", "user": {"login": "other"}, "submitted_at": "2026-10-13T08:40:00Z"},
            ],
            2: [],
            3: [
                {"state": "APPROVED", "user": {"login": "Rainnnee"}, "submitted_at": "2026-10-12T07:00:00Z"},
            ],
        }

    def get(self, url: str, *, search: bool = False) -> tuple[Any, dict[str, str]]:
        if url.endswith("/repos/Rainnnee/rainpiao"):
            return {"visibility": "public", "private": False, "default_branch": "main"}, {}
        if "/pulls/" in url:
            number = int(url.rsplit("/", 1)[1])
            return self.prs[number], {}
        if url.endswith("/commits/sunday"):
            return {
                "parents": [{"sha": "parent"}],
                "author": {"login": "Rainnnee"},
                "commit": {"author": {"date": "2026-10-12T06:59:00Z"}, "message": "Improve project notes"},
                "files": [{"filename": "docs/notes.md"}],
            }, {}
        if url.endswith("/commits/monday"):
            return {
                "parents": [{"sha": "parent"}],
                "author": {"login": "Rainnnee"},
                "commit": {"author": {"date": "2026-10-12T07:00:00Z"}, "message": "Start weekly work"},
                "files": [{"filename": "src/model.py"}],
            }, {}
        raise AssertionError(f"Unexpected API URL: {url}")

    def pages(self, url: str, *, search: bool = False) -> list[Any]:
        if "/commits?" in url:
            return [{"sha": "sunday"}, {"sha": "monday"}]
        if "/reviews?" in url:
            number = int(url.split("/pulls/")[1].split("/", 1)[0])
            return self.reviews[number]
        raise AssertionError(f"Unexpected paginated API URL: {url}")

    def search_prs(self, repo: str, qualifier: str, start: date, end_exclusive: date) -> list[dict[str, Any]]:
        if qualifier == "author:Rainnnee":
            return [{"number": 1}, {"number": 2}]
        if qualifier == "reviewed-by:Rainnnee":
            return [{"number": 1}, {"number": 2}, {"number": 3}]
        raise AssertionError(f"Unexpected search qualifier: {qualifier}")


class MetricRulesTests(unittest.TestCase):
    def test_local_date_respects_pacific_midnight_and_daylight_saving(self) -> None:
        self.assertEqual(local_day("2026-10-12T06:59:00Z"), date(2026, 10, 11))
        self.assertEqual(local_day("2026-10-12T07:00:00Z"), date(2026, 10, 12))
        self.assertEqual(local_day("2026-03-08T07:59:00Z"), date(2026, 3, 7))
        self.assertEqual(local_day("2026-03-08T08:00:00Z"), date(2026, 3, 8))

    def test_window_is_start_inclusive_and_end_exclusive(self) -> None:
        self.assertTrue(within("2026-07-19T07:00:00Z", date(2026, 7, 19), date(2026, 10, 17)))
        self.assertFalse(within("2026-10-17T07:00:00Z", date(2026, 7, 19), date(2026, 10, 17)))

    def test_meaningful_commit_exclusions_do_not_hide_real_docs_or_code(self) -> None:
        config = {
            "excluded_path_prefixes": ["vendor/", "node_modules/", "build/"],
            "dependency_only_filenames": ["package-lock.json", "requirements.txt"],
        }
        self.assertFalse(is_meaningful_commit([{"filename": "vendor/lib.js"}], config, "update vendor"))
        self.assertFalse(is_meaningful_commit([{"filename": "package-lock.json"}], config, "refresh dependencies"))
        self.assertFalse(is_meaningful_commit([{"filename": "src/model.py"}], config, "[bot] update"))
        self.assertTrue(is_meaningful_commit([{"filename": "docs/guide.md"}], config, "clarify setup"))
        self.assertTrue(is_meaningful_commit([{"filename": "vendor/lib.js"}, {"filename": "src/model.py"}], config, "refactor"))

    def test_activity_uses_merged_and_reviewed_events_with_correct_week_boundary(self) -> None:
        config = {"excluded_path_prefixes": [], "dependency_only_filenames": []}
        activity, window = fetch_activity(FakeGitHub(), ["Rainnnee/rainpiao"], config, date(2026, 10, 17))
        self.assertEqual(activity["merged_contributions_90d"], 1)
        self.assertEqual(activity["reviewed_by_others_90d"], 1)
        self.assertEqual(activity["technical_reviews_90d"], 1)
        self.assertEqual(activity["active_weeks"]["count"], 1)
        self.assertTrue(activity["active_weeks"]["weeks"][-1]["active"])
        self.assertTrue(activity["current_week"]["active"])
        trail = activity["activity_timeline_90d"]["weeks"]
        self.assertEqual(len(trail), 14)
        self.assertEqual(trail[-1]["merged_prs"], 1)
        self.assertEqual(trail[-1]["reviews_written"], 1)
        self.assertIn(0, trail[-1]["workdays"])
        self.assertEqual(window["end_date_exclusive"], "2026-10-17")

    def test_metrics_copy_uses_inclusive_display_dates_and_singular_project(self) -> None:
        data = {
            "status": "measured",
            "generated_at": "2026-10-17T19:51:39-07:00",
            "tracked_repositories": ["Rainnnee/rainpiao"],
            "window": {"end_date_exclusive": "2026-10-17"},
            "metrics": {
                "active_weeks": {"count": 1, "start_date": "2026-08-17", "end_date_exclusive": "2026-10-12"},
                "current_week": {"active": True},
                "merged_contributions_90d": 1,
                "reviewed_by_others_90d": 0,
                "technical_reviews_90d": 0,
                "verified_technical_projects": 1,
                "evaluation_reports": 0,
            },
            "projects": [{
                "title": "Sample project", "url": "https://example.test/",
                "setup_url": "https://example.test/setup", "verified_on": "2026-10-17",
            }],
        }
        rendered = readme_block(data)
        self.assertIn("2026-08-17 through 2026-10-11", rendered)
        self.assertIn("through 2026-10-16", rendered)
        self.assertIn("1 currently verified runnable project", rendered)
        self.assertIn("**Reviews written:** 0", rendered)

    def test_work_trail_uses_weekly_events_and_keeps_sparse_values_honest(self) -> None:
        data = {
            "generated_at": "2026-10-17T19:51:39-07:00",
            "metrics": {
                "active_weeks": {"count": 0, "total": 8},
                "current_week": {"active": True},
                "activity_timeline_90d": {
                    "start_date": "2026-07-19",
                    "end_date_exclusive": "2026-10-17",
                    "weeks": [
                        {"start_date": "2026-10-12", "workdays": [0, 3], "merged_prs": 7, "reviews_written": 1}
                    ],
                },
                "merged_contributions_90d": 7,
                "reviewed_by_others_90d": 0,
                "technical_reviews_90d": 1,
            },
        }
        rendered = work_trail_svg(data)
        self.assertIn("THE WORK TRAIL", rendered)
        self.assertIn("CURRENT PARTIAL WEEK", rendered)
        self.assertIn("days with qualifying commits", rendered)

    def test_unmeasured_profile_is_explicitly_distinct_from_zero(self) -> None:
        data = {
            "status": "not_measured_yet",
            "generated_at": None,
            "tracked_repositories": ["Rainnnee/rainpiao"],
            "metrics": {
                "active_weeks": {"count": None, "total": 8, "weeks": []},
                "current_week": {"active": None},
                "merged_contributions_90d": None,
                "reviewed_by_others_90d": None,
                "verified_technical_projects": 0,
                "evaluation_reports": 0,
            },
        }
        rendered = readme_block(data)
        self.assertIn("Not measured yet", rendered)
        self.assertIn("Empty evidence counts are separate from unmeasured activity", rendered)

    def test_private_repository_is_refused(self) -> None:
        class PrivateGitHub(FakeGitHub):
            def get(self, url: str, *, search: bool = False) -> tuple[Any, dict[str, str]]:
                if url.endswith("/repos/Rainnnee/rainpiao"):
                    return {"visibility": "private", "private": True, "default_branch": "main"}, {}
                return super().get(url, search=search)

        with self.assertRaises(CollectionError):
            fetch_activity(PrivateGitHub(), ["Rainnnee/rainpiao"], {}, date(2026, 10, 17))

    def test_failed_public_fetch_preserves_last_good_generated_files(self) -> None:
        generated_paths = [
            ROOT / "README.md",
            ROOT / "assets/work-trail.svg",
            ROOT / "assets/proof.svg",
            ROOT / "data/metrics.json",
            ROOT / "data/history.json",
        ]
        before = {path: path.read_bytes() for path in generated_paths}

        class FailingGitHub:
            def get(self, url: str, *, search: bool = False) -> tuple[Any, dict[str, str]]:
                raise CollectionError("simulated partial API failure")

        with patch("collect_metrics.GitHub", return_value=FailingGitHub()):
            with redirect_stdout(StringIO()), redirect_stderr(StringIO()):
                self.assertEqual(main(), 1)
        self.assertEqual(before, {path: path.read_bytes() for path in generated_paths})


class EvidenceLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "evidence.json"
        self.today = date(2026, 10, 17)
        self.project = {
            "id": "portfolio", "title": "Portfolio", "url": "https://example.test/",
            "visibility": "public", "revision": "abc123", "role": "Personal project",
            "setup_url": "https://example.test/setup", "run_command": "python3 -m http.server 8000",
            "data_source": "Static files", "verification_scope": "Served local pages",
            "expected_output": "Home page responds", "verified_on": "2026-10-17",
            "verification_result": "passed",
        }
        self.report = {
            "id": "report-1", "title": "Evaluation", "project_id": "portfolio",
            "url": "https://example.test/report", "visibility": "public",
            "question": "Does the change help?", "protocol_url": "https://example.test/protocol",
            "result_interpretation": "It helps in this test.", "limitations": "Small sample.",
            "evidence_url": "https://example.test/evidence", "result_date": "2026-10-17",
            "review_status": "self-reviewed", "status": "published",
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def write_ledger(self, projects: list[dict[str, Any]], reports: list[dict[str, Any]]) -> None:
        self.path.write_text(json.dumps({"schema_version": 1, "projects": projects, "reports": reports}), encoding="utf-8")

    def test_only_current_public_passed_projects_count_and_report_versions_deduplicate(self) -> None:
        private = {**self.project, "id": "private", "visibility": "private"}
        expired = {**self.project, "id": "expired", "verified_on": "2026-07-18"}
        failed = {**self.project, "id": "failed", "verification_result": "failed"}
        private_report = {**self.report, "id": "private-report", "visibility": "private"}
        draft = {**self.report, "id": "draft", "status": "draft"}
        duplicate_version = {**self.report, "title": "Evaluation, revised", "result_date": "2026-10-18"}
        self.write_ledger([self.project, private, expired, failed], [self.report, duplicate_version, private_report, draft])
        projects, reports = verified_evidence(self.path, self.today)
        self.assertEqual([item["id"] for item in projects], ["portfolio"])
        self.assertEqual([item["id"] for item in reports], ["report-1"])

    def test_published_report_requires_evidence_fields(self) -> None:
        incomplete = {**self.report, "limitations": ""}
        self.write_ledger([self.project], [incomplete])
        with self.assertRaises(CollectionError):
            verified_evidence(self.path, self.today)

    def test_duplicate_project_ids_fail_closed(self) -> None:
        self.write_ledger([self.project, {**self.project, "revision": "different"}], [])
        with self.assertRaises(CollectionError):
            verified_evidence(self.path, self.today)


class PaginationTests(unittest.TestCase):
    def test_rest_pagination_collects_all_pages(self) -> None:
        client = GitHub()
        responses = iter([
            ([1], {"link": '<https://api.github.com/page2>; rel="next"'}),
            ([2], {}),
        ])
        client.get = lambda url, search=False: next(responses)  # type: ignore[method-assign]
        self.assertEqual(client.pages("https://api.github.com/page1"), [1, 2])

    def test_incomplete_search_results_fail_closed(self) -> None:
        client = GitHub()
        client.get = lambda url, search=False: ({"items": [], "incomplete_results": True, "total_count": 1}, {})  # type: ignore[method-assign]
        with self.assertRaises(CollectionError):
            client.pages("https://api.github.com/search/issues", search=True)


if __name__ == "__main__":
    unittest.main()
