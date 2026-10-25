"""Checks for calendar integrity, honest counting, and theme-safe SVG output."""
import importlib.util
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

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
