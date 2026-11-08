"""Checks for calendar integrity, honest counting, and theme-safe SVG output."""
import importlib.util
import io
import json
from urllib.error import HTTPError, URLError
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch, call

spec = importlib.util.spec_from_file_location("profile_activity", Path(__file__).resolve().parents[1] / "scripts/update_profile_activity.py")
activity = importlib.util.module_from_spec(spec)
spec.loader.exec_module(activity)


def calendar(year=2026, counts=None):
    counts = counts or {}
    day, end = date(year, 1, 1), date(year + 1, 1, 1)
    days = {}
    while day < end:
        count = counts.get(day.isoformat(), 0)
        days[day.isoformat()] = {"count": count, "level": min(count, 4)}
        day += timedelta(days=1)
    return {"year": year, "total": sum(counts.values()), "days": days}


def document(snapshot):
    parts = [f'<h2 id="js-contribution-activity-description">{snapshot["total"]} contributions in {snapshot["year"]}</h2>']
    for day, cell in snapshot["days"].items():
        parts.append(f'<td id="day-{day}" data-date="{day}" data-level="{cell["level"]}"></td>')
        count = cell["count"]
        text = "No contributions" if not count else f"{count} contributions"
        parts.append(f'<tool-tip for="day-{day}">{text} on this date</tool-tip>')
    return "".join(parts)


class CalendarTests(unittest.TestCase):
    def test_leap_year_and_total_are_preserved(self):
        snapshot = calendar(2024, {"2024-02-29": 4})
        parsed = activity.parse_contribution_calendar(document(snapshot), 2024)
        self.assertEqual(len(parsed["days"]), 366)
        self.assertEqual(parsed["total"], 4)
        self.assertEqual(parsed["days"]["2024-02-29"]["count"], 4)

    def test_rejects_missing_day_or_wrong_year(self):
        snapshot = calendar()
        del snapshot["days"]["2026-01-01"]
        with self.assertRaises(activity.CollectionError):
            activity.parse_contribution_calendar(document(snapshot), 2026)
        with self.assertRaises(activity.CollectionError):
            activity.parse_contribution_calendar(document(calendar()), 2025)

    def test_rejects_total_mismatch(self):
        snapshot = calendar(counts={"2026-02-01": 3})
        snapshot["total"] = 4
        with self.assertRaises(activity.CollectionError):
            activity.parse_contribution_calendar(document(snapshot), 2026)

    def test_streak_keeps_yesterday_and_ignores_future(self):
        snapshot = calendar(counts={"2026-01-01": 1, "2026-01-02": 1, "2026-01-03": 1, "2026-10-20": 2, "2026-10-21": 1, "2026-12-01": 10})
        self.assertEqual(activity.streaks(snapshot, date(2026, 10, 22)), (2, 3, 5))
        self.assertEqual(activity.streaks(snapshot, date(2026, 10, 23)), (0, 3, 5))


class RequestRetryTests(unittest.TestCase):
    def test_calendar_recovers_from_gateway_timeout(self):
        snapshot = calendar(counts={"2026-10-21": 3})
        error = HTTPError("https://github.com", 504, "Gateway Timeout", {}, None)
        with patch.dict(activity.os.environ, {"GITHUB_TOKEN": ""}), patch.object(activity, "urlopen", side_effect=[error, io.BytesIO(document(snapshot).encode())]) as request, patch.object(activity, "sleep") as sleep:
            self.assertEqual(activity.fetch_calendar(2026), snapshot)
        self.assertEqual(request.call_count, 2)
        sleep.assert_called_once_with(2)

    def test_api_recovers_from_transport_timeout(self):
        with patch.object(activity, "urlopen", side_effect=[URLError("timed out"), TimeoutError(), io.BytesIO(b'{"total_count": 3}')]) as request, patch.object(activity, "sleep") as sleep:
            self.assertEqual(activity.api_json("/search/commits"), {"total_count": 3})
        self.assertEqual(request.call_count, 3)
        self.assertEqual(sleep.call_args_list, [call(2), call(4)])

    def test_permanent_http_errors_are_not_retried(self):
        for status in (401, 403, 404):
            error = HTTPError("https://api.github.com", status, "Denied", {}, None)
            with self.subTest(status=status), patch.object(activity, "urlopen", side_effect=error) as request, patch.object(activity, "sleep") as sleep:
                with self.assertRaises(activity.CollectionError):
                    activity.api_json("/users/Rainnnee")
                self.assertEqual(request.call_count, 1)
                sleep.assert_not_called()

    def test_exhausted_retries_keep_previous_files(self):
        error = HTTPError("https://github.com", 504, "Gateway Timeout", {}, None)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "data/profile-activity.json"
            target.parent.mkdir()
            target.write_text("previous snapshot")
            with patch.dict(activity.os.environ, {"GITHUB_TOKEN": ""}), patch.object(activity, "ROOT", root), patch.object(activity, "urlopen", side_effect=error) as request, patch.object(activity, "sleep") as sleep:
                with self.assertRaises(activity.CollectionError):
                    activity.main()
                self.assertEqual(request.call_count, 3)
                self.assertEqual(sleep.call_args_list, [call(2), call(4)])
            self.assertEqual(target.read_text(), "previous snapshot")
            self.assertFalse((root / "assets").exists())


class ApiCalendarTests(unittest.TestCase):
    @staticmethod
    def response(request):
        variables = json.loads(request.data)["variables"]
        start, end = (date.fromisoformat(variables[key][:10]) for key in ("from", "to"))
        cells = []
        for ordinal in range(start.toordinal(), end.toordinal() + 1):
            day = date.fromordinal(ordinal).isoformat()
            count = 2 if day.endswith("02-29") else 0
            cells.append({"date": day, "contributionCount": count,
                          "contributionLevel": "SECOND_QUARTILE" if count else "NONE"})
        return json.dumps({"data": {"user": {"contributionsCollection": {"contributionCalendar": {
            "totalContributions": sum(c["contributionCount"] for c in cells),
            "weeks": [{"contributionDays": cells}]}}}}}).encode()

    def test_quarterly_api_preserves_leap_day_and_total(self):
        with patch.dict(activity.os.environ, {"GITHUB_TOKEN": "test-token"}), patch.object(activity, "read_github", side_effect=self.response) as read:
            snapshot = activity.fetch_api_calendar(2024, "Rainnnee", date(2025, 1, 1))
        self.assertEqual(read.call_count, 4)
        self.assertEqual(len(snapshot["days"]), 366)
        self.assertEqual(snapshot["total"], 2)
        self.assertEqual(snapshot["days"]["2024-02-29"], {"count": 2, "level": 2})
        windows = [json.loads(c.args[0].data)["variables"] for c in read.call_args_list]
        self.assertEqual(windows[0]["to"], "2024-03-31T23:59:59Z")
        self.assertEqual(windows[1]["from"], "2024-04-01T00:00:00Z")

    def test_current_year_only_requests_elapsed_days(self):
        with patch.dict(activity.os.environ, {"GITHUB_TOKEN": "test-token"}), patch.object(activity, "read_github", side_effect=self.response) as read:
            snapshot = activity.fetch_api_calendar(2026, "Rainnnee", date(2026, 1, 3))
        self.assertEqual(read.call_count, 1)
        self.assertEqual(json.loads(read.call_args.args[0].data)["variables"]["to"], "2026-01-03T23:59:59Z")
        self.assertEqual(len(snapshot["days"]), 365)
        self.assertEqual(snapshot["days"]["2026-12-31"], {"count": 0, "level": 0})

    def test_rejects_api_errors_missing_days_and_wrong_totals(self):
        def damaged(request, mode):
            payload = json.loads(self.response(request))
            calendar = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
            if mode == "errors":
                payload["errors"] = [{"message": "resource limit"}]
            elif mode == "missing":
                calendar["weeks"][0]["contributionDays"].pop()
            elif mode == "duplicate":
                calendar["weeks"][0]["contributionDays"].append(calendar["weeks"][0]["contributionDays"][0])
            else:
                calendar["totalContributions"] += 1
            return json.dumps(payload).encode()
        for mode in ("errors", "missing", "duplicate", "total"):
            with self.subTest(mode=mode), patch.dict(activity.os.environ, {"GITHUB_TOKEN": "test-token"}), patch.object(activity, "read_github", side_effect=lambda request: damaged(request, mode)):
                with self.assertRaises(activity.CollectionError):
                    activity.fetch_api_calendar(2026, "Rainnnee", date(2026, 1, 3))

    def test_workflow_uses_api_without_html_request(self):
        with patch.dict(activity.os.environ, {"GITHUB_TOKEN": "test-token"}), patch.object(activity, "fetch_api_calendar", return_value={"total": 0}) as api:
            self.assertEqual(activity.fetch_calendar(2026), {"total": 0})
            api.assert_called_once_with(2026, "Rainnnee")


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.metrics = dict(commits=26, prs=9, issues=0, reviews=0, stars=0, repos=2, followers=1, rank="C", languages={"C++": 20, "A&B": 10})
        self.snapshot = calendar(counts={"2026-10-21": 3})
        self.now = datetime(2026, 10, 22, 14, 0, tzinfo=activity.TIMEZONE)

    def test_rank_uses_upstream_all_commit_thresholds(self):
        zero = dict(commits=0, prs=0, issues=0, reviews=0, stars=0, followers=0)
        median = dict(commits=1000, prs=50, issues=25, reviews=2, stars=50, followers=10)
        self.assertEqual(activity.activity_rank(zero), "C")
        self.assertEqual(activity.activity_rank(median), "B+")

    def test_both_themes_are_valid_and_escape_source_text(self):
        for theme in activity.THEMES:
            for svg in (activity.build_svg(self.snapshot, self.now, theme), activity.build_overview_svg(self.metrics, self.snapshot, self.now, theme), activity.build_languages_svg(self.metrics, theme)):
                root = ET.fromstring(svg)
                self.assertEqual(root.attrib["viewBox"].split()[:3], ["0", "0", "960"])
                self.assertIn(activity.THEMES[theme]["text"], svg)
                self.assertIn("'Segoe UI'", svg)
                self.assertNotIn("MY GITHUB RHYTHM", svg)
            self.assertIn("A&amp;B", activity.build_languages_svg(self.metrics, theme))

    def test_language_colors_follow_names_when_order_changes(self):
        for theme in activity.THEMES:
            for languages in ({"Python": 60, "JavaScript": 40}, {"JavaScript": 60, "Python": 40}):
                svg = activity.build_languages_svg({"languages": languages}, theme)
                root = ET.fromstring(svg)
                circles = root.findall("{http://www.w3.org/2000/svg}circle")
                self.assertEqual([c.attrib["fill"] for c in circles],
                                 [activity.LANGUAGE_COLORS[name] for name in languages])
            unknown = activity.build_languages_svg({"languages": {"Unlisted language": 1}}, theme)
            self.assertIn('fill="#8b949e"', unknown)

    def test_collect_failure_does_not_replace_previous_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "data/profile-activity.json"
            target.parent.mkdir()
            target.write_text("previous snapshot")
            with patch.object(activity, "ROOT", root), patch.object(activity, "fetch_calendar", return_value=self.snapshot), patch.object(activity, "fetch_public_stats", side_effect=activity.CollectionError("API unavailable")):
                with self.assertRaises(activity.CollectionError):
                    activity.main()
            self.assertEqual(target.read_text(), "previous snapshot")
            self.assertFalse((root / "assets").exists())


if __name__ == "__main__":
    unittest.main()
