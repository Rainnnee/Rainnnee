#!/usr/bin/env python3
"""Build a small, accurate profile dashboard from GitHub's own calendar."""

from __future__ import annotations

import html
import json
import os
import re
import tempfile
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


def fetch_calendar(year: int, login: str = LOGIN) -> dict[str, object]:
    url = SOURCE_URL.format(login=login, year=year)
    request = Request(url, headers={"User-Agent": "Rainnnee-GitHub-profile/1.0", "Accept": "text/html"})
    try:
        with urlopen(request, timeout=30) as response:
            document = response.read().decode("utf-8")
    except Exception as exc:
        raise CollectionError(f"Could not read the GitHub contribution calendar: {exc}") from exc
    return parse_contribution_calendar(document, year)


def build_svg(snapshot: dict[str, object], refreshed_at: datetime) -> str:
    year = int(snapshot["year"])
    total = int(snapshot["total"])
    days = snapshot["days"]
    assert isinstance(days, dict)
    first_day = date(year, 1, 1)
    first_sunday = first_day.toordinal() - ((first_day.weekday() + 1) % 7)
    month_labels: list[str] = []
    squares: list[str] = []
    month_sums = [0] * 12

    for day_text, cell in sorted(days.items()):
        current = date.fromisoformat(day_text)
        col = (current.toordinal() - first_sunday) // 7
        row = (current.weekday() + 1) % 7
        x, y = 35 + col * 14, 128 + row * 13
        level, count = int(cell["level"]), int(cell["count"] or 0)
        month_sums[current.month - 1] += count
        squares.append(
            f'<rect x="{x}" y="{y}" width="10" height="10" rx="2" fill="{CELL_COLORS[level]}">'
            f'<title>{current.isoformat()}: {count} contribution{"s" if count != 1 else ""}</title></rect>'
        )
        if current.day == 1:
            month_labels.append(
                f'<text x="{x}" y="113" class="month">{html.escape(current.strftime("%b"))}</text>'
            )

    max_month = max(month_sums, default=0) or 1
    monthly_bars: list[str] = []
    baseline, max_bar_height = 306, 25
    for index, count in enumerate(month_sums):
        x = 52 + index * 57
        height = round(count / max_month * max_bar_height) if count else 2
        color = "#E994C1" if index >= refreshed_at.month - 1 else "#4A9FE0"
        monthly_bars.append(
            f'<rect x="{x}" y="{baseline-height}" width="26" height="{height}" rx="4" fill="{color}">'
            f'<title>{date(year, index+1, 1).strftime("%B")}: {count} contributions</title></rect>'
            f'<text x="{x+13}" y="326" text-anchor="middle" class="month">{date(year, index+1, 1).strftime("%b")}</text>'
        )

    refreshed = refreshed_at.astimezone(TIMEZONE).strftime("%b %-d, %Y")
    description = f"GitHub contribution calendar for {year}: {total} contributions. Activity is shown day by day, with monthly totals below. Refreshed {refreshed}."
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 350" role="img" aria-labelledby="title desc">
<title id="title">Rain Piao's GitHub activity in {year}</title>
<desc id="desc">{html.escape(description)}</desc>
<style>
.title{{font:700 25px Arial,sans-serif;fill:#173F70;letter-spacing:.2px}}
.subtitle{{font:14px Arial,sans-serif;fill:#436F9B;letter-spacing:.45px}}
.month{{font:12px Arial,sans-serif;fill:#547795}}
.count{{font:700 50px Arial,sans-serif;fill:#173F70}}
.label{{font:700 13px Arial,sans-serif;fill:#436F9B;letter-spacing:.55px}}
.micro{{font:12px Arial,sans-serif;fill:#547795}}
</style>
<rect x="1" y="1" width="1118" height="348" rx="22" fill="#FFFEFD" stroke="#D4E5F0" stroke-width="2"/>
<path d="M28 12h214" stroke="#238BDF" stroke-width="6" stroke-linecap="round"/>
<path d="M256 12h118" stroke="#E994C1" stroke-width="6" stroke-linecap="round"/>
<text x="34" y="52" class="title">MY GITHUB RHYTHM ✨</text>
<text x="36" y="77" class="subtitle">CONTRIBUTION CALENDAR · {year}</text>
<text x="1080" y="49" text-anchor="end" class="micro">UPDATED {html.escape(refreshed.upper())}</text>
{''.join(month_labels)}
{''.join(squares)}
<text x="36" y="247" class="label">MONTHLY CONTRIBUTIONS</text>
<line x1="35" y1="306" x2="748" y2="306" stroke="#D4E5F0" stroke-width="1"/>
{''.join(monthly_bars)}
<line x1="790" y1="83" x2="790" y2="324" stroke="#D4E5F0" stroke-width="2"/>
<text x="835" y="118" class="label">YEAR-TO-DATE</text>
<text x="832" y="182" class="count">{total}</text>
<text x="836" y="208" class="label">GITHUB CONTRIBUTIONS</text>
<text x="836" y="231" class="micro">{year} · according to your profile calendar</text>
<rect x="835" y="263" width="230" height="36" rx="18" fill="#EAF5FB"/>
<circle cx="855" cy="281" r="5" fill="#4A9FE0"/>
<circle cx="871" cy="281" r="5" fill="#E994C1"/>
<text x="888" y="285" class="micro">Daily rhythm · monthly view</text>
</svg>'''


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
    snapshot["login"] = LOGIN
    snapshot["refreshed_at"] = now.isoformat(timespec="seconds")
    data = json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n"
    svg = build_svg(snapshot, now)
    write_atomic(ROOT / "data/profile-activity.json", data)
    write_atomic(ROOT / "assets/github-activity.svg", svg)
    print(f"Updated {snapshot['total']} GitHub contributions for {snapshot['year']}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
