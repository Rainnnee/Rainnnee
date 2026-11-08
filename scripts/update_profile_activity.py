#!/usr/bin/env python3
"""Render theme-aware profile stats from public GitHub data."""

from __future__ import annotations

import html
import json
import os
import re
import tempfile
import sys
from time import sleep
from urllib.error import HTTPError, URLError
from datetime import date, datetime
from html.parser import HTMLParser
from pathlib import Path
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
LOGIN = "Rainnnee"
TIMEZONE = ZoneInfo("America/Los_Angeles")
SOURCE_URL = "https://github.com/users/{login}/contributions?from={year}-01-01&to={year}-12-31"
CELL_COLORS = ("#EFF5F9", "#C6E7F6", "#8BCDF0", "#4A9FE0", "#E994C1")


class CollectionError(RuntimeError):
    """The public contribution calendar could not be safely interpreted."""


class ContributionParser(HTMLParser):
    """Read the total, day intensity, and tooltip count from GitHub's calendar."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.heading = ""
        self.cells: dict[str, dict[str, int | None]] = {}
        self._heading = False
        self._tooltip_date: str | None = None
        self._tooltip_text: dict[str, str] = {}
        self._id_to_date: dict[str, str] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        if tag == "h2" and attributes.get("id") == "js-contribution-activity-description":
            self._heading = True
        elif tag == "td" and attributes.get("data-date") and attributes.get("data-level") is not None:
            day = attributes["data-date"]
            cell_id = attributes.get("id")
            try:
                level = int(attributes["data-level"] or "0")
                parsed_day = date.fromisoformat(day or "")
            except (ValueError, TypeError) as exc:
                raise CollectionError("GitHub returned an invalid contribution day") from exc
            if level not in range(len(CELL_COLORS)):
                raise CollectionError("GitHub returned an unknown contribution intensity")
            self.cells[parsed_day.isoformat()] = {"level": level, "count": None}
            if cell_id:
                self._id_to_date[cell_id] = parsed_day.isoformat()
        elif tag == "tool-tip":
            self._tooltip_date = self._id_to_date.get(attributes.get("for", ""))

    def handle_data(self, data: str) -> None:
        if self._heading:
            self.heading += data
        if self._tooltip_date:
            self._tooltip_text[self._tooltip_date] = self._tooltip_text.get(self._tooltip_date, "") + data

    def handle_endtag(self, tag: str) -> None:
        if tag == "h2":
            self._heading = False
        elif tag == "tool-tip":
            self._tooltip_date = None

    def snapshot(self, requested_year: int) -> dict[str, object]:
        heading = " ".join(self.heading.split())
        match = re.search(r"(\d[\d,]*)\s+contributions?\s+in\s+(\d{4})", heading, re.IGNORECASE)
        if not match:
            raise CollectionError("GitHub's contribution total was missing or had an unexpected format")
        total, year = int(match.group(1).replace(",", "")), int(match.group(2))
        if year != requested_year:
            raise CollectionError(f"GitHub returned {year}'s calendar; expected {requested_year}")

        expected_days = {date(year, 1, 1).fromordinal(date(year, 1, 1).toordinal() + i).isoformat()
                         for i in range((date(year + 1, 1, 1) - date(year, 1, 1)).days)}
        if set(self.cells) != expected_days:
            raise CollectionError("GitHub's calendar did not contain one cell for every day in the year")

        for day, cell in self.cells.items():
            tooltip = " ".join(self._tooltip_text.get(day, "").split())
            if re.match(r"No contributions\b", tooltip, re.IGNORECASE):
                count = 0
            else:
                count_match = re.search(r"(\d[\d,]*)\s+contributions?\s+on\b", tooltip, re.IGNORECASE)
                if not count_match:
                    raise CollectionError(f"GitHub did not provide a readable contribution count for {day}")
                count = int(count_match.group(1).replace(",", ""))
            cell["count"] = count

        observed_total = sum(int(cell["count"] or 0) for cell in self.cells.values())
        if observed_total != total:
            raise CollectionError("GitHub's daily counts did not match its displayed yearly total")
        return {"year": year, "total": total, "days": self.cells}


def parse_contribution_calendar(document: str, year: int) -> dict[str, object]:
    parser = ContributionParser()
    parser.feed(document)
    return parser.snapshot(year)


def read_github(request: Request) -> bytes:
    """Retry temporary GitHub failures before giving up on the refresh."""
    for attempt in range(3):
        try:
            with urlopen(request, timeout=30) as response:
                return response.read()
        except HTTPError as exc:
            # Authentication, permissions, and missing resources need a real fix.
            if exc.code not in {408, 429, 500, 502, 503, 504} or attempt == 2:
                raise
            reason = f"HTTP {exc.code}"
            exc.close()
        except (URLError, TimeoutError, ConnectionError) as exc:
            if attempt == 2:
                raise
            reason = type(exc).__name__
        delay = 2 ** (attempt + 1)
        print(f"Temporary GitHub request failure ({reason}); retry {attempt + 1}/2 in {delay}s", file=sys.stderr)
        sleep(delay)
    raise AssertionError("unreachable")


def fetch_api_calendar(year: int, login: str, today: date | None = None) -> dict[str, object]:
    """Read bounded quarterly calendars through the authenticated public API."""
    today = today or datetime.now(TIMEZONE).date()
    first, end = date(year, 1, 1), min(date(year, 12, 31), today)
    if end < first:
        raise CollectionError("Cannot collect a future year's contribution calendar")
    days = {date.fromordinal(n).isoformat(): {"level": 0, "count": 0}
            for n in range(first.toordinal(), date(year, 12, 31).toordinal() + 1)}
    levels = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
              "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
    query = """query($login: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $login) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks { contributionDays { date contributionCount contributionLevel } }
          }
        }
      }
    }"""
    total = 0
    # Small queries stay below GitHub's contributionsCollection resource limits.
    for month in (1, 4, 7, 10):
        start = date(year, month, 1)
        if start > end:
            break
        next_quarter = date(year + 1, 1, 1) if month == 10 else date(year, month + 3, 1)
        stop = min(end, date.fromordinal(next_quarter.toordinal() - 1))
        body = json.dumps({"query": query, "variables": {"login": login,
            "from": f"{start.isoformat()}T00:00:00Z", "to": f"{stop.isoformat()}T23:59:59Z"}}).encode()
        request = Request("https://api.github.com/graphql", data=body, headers={
            "User-Agent": "Rainnnee-profile", "Content-Type": "application/json",
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}"})
        try:
            payload = json.loads(read_github(request))
            if payload.get("errors"):
                raise CollectionError("GitHub returned contribution API errors")
            calendar = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
            period = {}
            for week in calendar["weeks"]:
                for cell in week["contributionDays"]:
                    day = date.fromisoformat(cell["date"])
                    if not start <= day <= stop:
                        continue
                    count = cell["contributionCount"]
                    if type(count) is not int or count < 0 or day.isoformat() in period:
                        raise CollectionError("GitHub returned invalid or duplicate contribution counts")
                    level = levels[cell["contributionLevel"]]
                    if (count == 0) != (level == 0):
                        raise CollectionError("GitHub returned inconsistent contribution intensity")
                    period[day.isoformat()] = {"count": count, "level": level}
            expected = {date.fromordinal(n).isoformat()
                        for n in range(start.toordinal(), stop.toordinal() + 1)}
            observed = sum(cell["count"] for cell in period.values())
            if set(period) != expected or type(calendar["totalContributions"]) is not int or observed != calendar["totalContributions"]:
                raise CollectionError("GitHub's API calendar was incomplete or its total did not match")
        except CollectionError:
            raise
        except Exception as exc:
            raise CollectionError("Could not read the GitHub contribution API calendar") from exc
        days.update(period)
        total += observed
    return {"year": year, "total": total, "days": days}


def fetch_calendar(year: int, login: str = LOGIN) -> dict[str, object]:
    if os.environ.get("GITHUB_TOKEN"):
        return fetch_api_calendar(year, login)
    url = SOURCE_URL.format(login=login, year=year)
    request = Request(url, headers={"User-Agent": "Rainnnee-GitHub-profile/1.0", "Accept": "text/html"})
    try:
        document = read_github(request).decode("utf-8")
    except Exception as exc:
        raise CollectionError(f"Could not read the GitHub contribution calendar: {exc}") from exc
    return parse_contribution_calendar(document, year)


def api_json(path: str) -> object:
    """Read public API resources; a workflow token raises the rate limit."""
    headers = {"User-Agent": "Rainnnee-profile", "Accept": "application/vnd.github+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = Request("https://api.github.com" + path, headers=headers)
    try:
        return json.loads(read_github(request))
    except Exception as exc:
        raise CollectionError(f"Could not read GitHub API resource {path.split('?')[0]}: {exc}") from exc


def fetch_public_stats(login: str = LOGIN) -> dict[str, object]:
    from urllib.parse import urlencode

    profile = api_json(f"/users/{login}")
    if not isinstance(profile, dict) or profile.get("login", "").lower() != login.lower():
        raise CollectionError("GitHub returned an unexpected user")
    repositories = []
    page = 1
    while True:
        batch = api_json(f"/users/{login}/repos?per_page=100&type=owner&page={page}")
        if not isinstance(batch, list):
            raise CollectionError("GitHub returned an unreadable repository list")
        repositories.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    languages: dict[str, int] = {}
    stars = 0
    for repo in repositories:
        if repo.get("fork") or repo.get("private"):
            continue
        stars += int(repo["stargazers_count"])
        breakdown = api_json(f"/repos/{repo['full_name']}/languages")
        if not isinstance(breakdown, dict) or any(type(n) is not int or n < 0 for n in breakdown.values()):
            raise CollectionError("GitHub returned an unreadable language breakdown")
        for language, size in breakdown.items():
            languages[language] = languages.get(language, 0) + size

    def count(kind: str, query: str) -> int:
        result = api_json(f"/search/{kind}?" + urlencode({"q": query, "per_page": 1}))
        if not isinstance(result, dict) or result.get("incomplete_results") or type(result.get("total_count")) is not int:
            raise CollectionError(f"GitHub returned incomplete {kind} search results")
        return result["total_count"]

    metrics = {
        "commits": count("commits", f"author:{login} is:public"),
        "prs": count("issues", f"author:{login} type:pr is:public"),
        "issues": count("issues", f"author:{login} type:issue is:public"),
        "reviews": count("issues", f"reviewed-by:{login} -author:{login} type:pr is:public"),
        "repos": int(profile["public_repos"]),
        "stars": stars,
        "followers": int(profile["followers"]),
        "languages": dict(sorted(languages.items(), key=lambda item: (-item[1], item[0]))),
    }
    metrics["rank"] = activity_rank(metrics)
    return metrics


def activity_rank(metrics: dict[str, object]) -> str:
    """Adapted from github-readme-stats (MIT); see docs/third-party-notices.md."""
    exp = lambda value: 1 - 2 ** -value
    log = lambda value: value / (1 + value)
    score = 1 - (
        2 * exp(int(metrics["commits"]) / 1000)
        + 3 * exp(int(metrics["prs"]) / 50)
        + exp(int(metrics["issues"]) / 25)
        + exp(int(metrics["reviews"]) / 2)
        + 4 * log(int(metrics["stars"]) / 50)
        + log(int(metrics["followers"]) / 10)
    ) / 12
    for threshold, level in zip(
        (1, 12.5, 25, 37.5, 50, 62.5, 75, 87.5, 100),
        ("S", "A+", "A", "A-", "B+", "B", "B-", "C+", "C"),
    ):
        if score * 100 <= threshold:
            return level
    return "C"


THEMES = {
    "light": {"background": "#ffffff", "border": "#d7e4f4", "text": "#203858", "muted": "#536b88", "accent": "#1769d2", "track": "#e8f1fb", "cells": ("#edf3fb", "#c2e8f7", "#6ccdea", "#248dd4", "#c94b9a"), "metrics": ("#087da5", "#1769d2", "#b33580", "#7650bd")},
    "dark": {"background": "#0d1117", "border": "#293d59", "text": "#dfebfa", "muted": "#a7bdd7", "accent": "#39c9f0", "track": "#17283f", "cells": ("#172338", "#174a70", "#0e86bb", "#29bbe5", "#f09acf"), "metrics": ("#39c9f0", "#75a8ff", "#f59bcf", "#bba0ff")},
}
# GitHub Linguist colors stay attached to names when repository rankings change.
LANGUAGE_COLORS = json.loads((ROOT / "data/language-colors.json").read_text())


def svg_shell(title: str, description: str, height: int, theme: str, content: str) -> str:
    palette = THEMES[theme]
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 960 {height}" role="img" aria-labelledby="title desc">
<title id="title">{html.escape(title)}</title>
<desc id="desc">{html.escape(description)}</desc>
<style>
text{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;fill:{palette['text']}}}
.heading{{font-size:19px;font-weight:600;letter-spacing:-.2px;fill:{palette["accent"]}}}
.label{{font-size:15px;fill:{palette['muted']}}}
.small{{font-size:13px;fill:{palette['muted']}}}
.value{{font-size:34px;font-weight:600;letter-spacing:-.6px}}
.month{{font-size:13px;fill:{palette['muted']}}}
</style>
<defs><linearGradient id="banner-accent"><stop stop-color="#23bce5"/><stop offset=".5" stop-color="#4b83f5"/><stop offset="1" stop-color="#f17db9"/></linearGradient></defs>
<rect x=".75" y=".75" width="958.5" height="{height-1.5}" rx="12" fill="{palette['background']}" stroke="{palette['border']}" stroke-width="1.5"/>
<path d="M14 1h932" stroke="url(#banner-accent)" stroke-width="2"/>
{content}
</svg>'''


def timestamp_text(now: datetime) -> str:
    return now.astimezone(TIMEZONE).strftime("%b %d, %H:%M %Z")


def build_overview_svg(metrics: dict[str, object], snapshot: dict[str, object], now: datetime, theme: str) -> str:
    p = THEMES[theme]
    parts = [f'<text x="26" y="36" class="heading">Public GitHub activity</text>',
             f'<text x="934" y="36" text-anchor="end" class="small">Updated {timestamp_text(now)}</text>']
    items = [(snapshot["total"], "Contributions", str(snapshot["year"])),
             (metrics["commits"], "Commits", "Public · all time"),
             (metrics["prs"], "Pull requests", "Public · all time"),
             (metrics["repos"], "Repositories", "Public")]
    for index, (value, label, scope) in enumerate(items):
        x = 28 + index * 178
        parts.append(f'<text x="{x}" y="100" class="value" style="fill:{p["metrics"][index]}">{value:,}</text><text x="{x}" y="128" class="label">{label}</text><text x="{x}" y="150" class="small">{scope}</text>')
    parts.extend([
        f'<line x1="751" y1="64" x2="751" y2="154" stroke="{p["border"]}"/>',
        f'<circle cx="850" cy="103" r="37" fill="none" stroke="{p["accent"]}" stroke-width="3"/>',
        f'<text x="850" y="115" text-anchor="middle" class="value" style="fill:{p["accent"]}">{metrics["rank"]}</text>',
        '<text x="850" y="162" text-anchor="middle" class="small">Activity rank</text>',
    ])
    return svg_shell("Public GitHub activity", f"{snapshot['year']}: {snapshot['total']} contributions. {metrics['commits']} public commits, {metrics['prs']} pull requests, and {metrics['repos']} public repositories. Activity rank {metrics['rank']}.", 185, theme, "".join(parts))


def streaks(snapshot: dict[str, object], today: date) -> tuple[int, int, int]:
    days = snapshot["days"]
    assert isinstance(days, dict)
    counts = {date.fromisoformat(day): int(cell["count"]) for day, cell in days.items() if date.fromisoformat(day) <= today}
    current = 0
    start = today if counts.get(today, 0) else today.fromordinal(today.toordinal() - 1)
    while counts.get(start, 0) > 0:
        current += 1
        start = start.fromordinal(start.toordinal() - 1)
    longest = run = active = 0
    for day, count in sorted(counts.items()):
        if count > 0:
            active += 1
            run += 1
            longest = max(longest, run)
        else:
            run = 0
    return current, longest, active


def build_svg(snapshot: dict[str, object], refreshed_at: datetime, theme: str = "light") -> str:
    year = int(snapshot["year"])
    days = snapshot["days"]
    assert isinstance(days, dict)
    today = refreshed_at.astimezone(TIMEZONE).date()
    first_day = date(year, 1, 1)
    first_sunday = first_day.toordinal() - ((first_day.weekday() + 1) % 7)
    current, longest, active = streaks(snapshot, today)
    p = THEMES[theme]
    parts = [f'<text x="26" y="36" class="heading">Contribution activity · {year}</text>',
             f'<text x="934" y="36" text-anchor="end" class="small">{active} active days</text>',
             f'<text x="26" y="66" class="label">Current streak  {current} {"day" if current == 1 else "days"}</text>',
             f'<text x="255" y="66" class="label">Longest streak  {longest} {"day" if longest == 1 else "days"} this year</text>']
    for day_text, cell in sorted(days.items()):
        day = date.fromisoformat(day_text)
        col = (day.toordinal() - first_sunday) // 7
        row = (day.weekday() + 1) % 7
        x, y = 58 + col * 16, 109 + row * 16
        level, count = int(cell["level"]), int(cell["count"])
        opacity = '.35' if day > today else '1'
        parts.append(f'<rect x="{x}" y="{y}" width="12" height="12" rx="2" fill="{p["cells"][level]}" opacity="{opacity}"><title>{day_text}: {count} contributions</title></rect>')
        if day.day == 1:
            parts.append(f'<text x="{x}" y="97" class="month">{day.strftime("%b")}</text>')
    for label, row in (("Mon", 1), ("Wed", 3), ("Fri", 5)):
        parts.append(f'<text x="26" y="{119+row*16}" class="small">{label}</text>')
    parts.append('<text x="26" y="245" class="small">Daily contributions, as shown on GitHub</text>')
    parts.append('<text x="772" y="245" class="small">Less</text>')
    for i, color in enumerate(p["cells"]):
        parts.append(f'<rect x="{810+i*16}" y="234" width="12" height="12" rx="2" fill="{color}"/>')
    parts.append('<text x="897" y="245" class="small">More</text>')
    return svg_shell(f"Contribution activity in {year}", f"{snapshot['total']} contributions in {year}. {active} active days; current streak {current} days; longest streak this year {longest} days. Updated {timestamp_text(refreshed_at)}.", 264, theme, "".join(parts))


def build_languages_svg(metrics: dict[str, object], theme: str) -> str:
    languages = metrics["languages"]
    assert isinstance(languages, dict)
    values = list(languages.items())
    if len(values) > 6:
        values = values[:5] + [("Other", sum(size for _, size in values[5:]))]
    total = sum(size for _, size in values)
    parts = ['<text x="26" y="36" class="heading">Languages in public repositories</text>',
             '<text x="934" y="36" text-anchor="end" class="small">By source-code volume</text>',
             '<defs><clipPath id="bar"><rect x="26" y="58" width="908" height="10" rx="5"/></clipPath></defs>']
    offset = 26.0
    for index, (language, size) in enumerate(values):
        share = size / total if total else 0
        width = 908 * share
        color = LANGUAGE_COLORS.get(language, "#8b949e")
        parts.append(f'<rect x="{offset:.2f}" y="58" width="{width:.2f}" height="10" fill="{color}" clip-path="url(#bar)"/>')
        x, y = 26 + index % 3 * 310, 97 + index // 3 * 29
        parts.append(f'<circle cx="{x+5}" cy="{y-5}" r="4" fill="{color}"/><text x="{x+17}" y="{y}" class="label">{html.escape(language)}  {share*100:.1f}%</text>')
        offset += width
    if not total:
        parts.append('<text x="26" y="98" class="label">No public language data available.</text>')
    return svg_shell("Languages in public repositories", "; ".join(f"{name}: {size} bytes" for name, size in values) or "No public language data", 148, theme, "".join(parts))


def write_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8") as stream:
            stream.write(content)
        os.replace(temporary, path)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise


def main() -> int:
    now = datetime.now(TIMEZONE)
    snapshot = fetch_calendar(now.year)
    metrics = fetch_public_stats()
    snapshot.update(login=LOGIN, refreshed_at=now.isoformat(timespec="seconds"))
    payload = {"login": LOGIN, "refreshed_at": snapshot["refreshed_at"], "metrics": metrics}
    # Collect and render everything before touching the last successful snapshot.
    outputs = {
        ROOT / "data/profile-activity.json": json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n",
        ROOT / "data/github-stats.json": json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
    }
    for theme in THEMES:
        outputs[ROOT / f"assets/github-overview-{theme}.svg"] = build_overview_svg(metrics, snapshot, now, theme)
        outputs[ROOT / f"assets/github-activity-{theme}.svg"] = build_svg(snapshot, now, theme)
        outputs[ROOT / f"assets/github-languages-{theme}.svg"] = build_languages_svg(metrics, theme)
    outputs[ROOT / "assets/github-activity.svg"] = build_svg(snapshot, now)
    for path, content in outputs.items():
        write_atomic(path, content)
    print(f"Updated {snapshot['total']} contributions, {metrics['commits']} public commits, and {metrics['prs']} pull requests.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
