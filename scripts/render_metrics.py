#!/usr/bin/env python3
"""Render the profile's contribution trail and inspectable-work panels."""

from __future__ import annotations

import html
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]

NAVY = "#173F70"
BLUE = "#238BDF"
PINK = "#E994C1"
SKY = "#D8EDFA"
MIST = "#EEF6FB"
ROSE_TEXT = "#87365F"
MID_BLUE = "#315F91"
LINE = "#C7DBE9"
PAPER = "#FFFAF7"


def fmt_date(value: str | None) -> str:
    if not value:
        return "Not measured yet"
    local = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(ZoneInfo("America/Los_Angeles"))
    return local.strftime("%b %-d, %Y")


def work_trail_svg(data: dict[str, Any]) -> str:
    metrics = data["metrics"]
    active = metrics["active_weeks"]
    count = active.get("count")
    active_text = "—" if count is None else str(count)
    total = active.get("total", 8)
    current = metrics.get("current_week", {}).get("active")
    current_text = "not measured" if current is None else "active" if current else "not active"
    timeline = metrics.get("activity_timeline_90d", {})
    weeks = timeline.get("weeks", [])
    columns = 14
    chart_x = 191
    col_step = 40
    cell_size = 5
    day_step = 7

    month_marks: list[str] = []
    previous_month: int | None = None
    work_cells: list[str] = []
    merge_bars: list[str] = []
    review_bars: list[str] = []
    for index in range(columns):
        week = weeks[index] if index < len(weeks) else {}
        try:
            start_day = date.fromisoformat(week.get("start_date", ""))
            if start_day.month != previous_month:
                x = chart_x + index * col_step
                month_marks.append(
                    f'<text x="{x}" y="107" class="month">{html.escape(start_day.strftime("%b").upper())}</text>'
                )
                previous_month = start_day.month
        except ValueError:
            pass

        active_days = set(week.get("workdays", []))
        if weeks:
            for weekday in range(7):
                x = chart_x + index * col_step
                y = 126 + weekday * day_step
                fill = BLUE if weekday in active_days else MIST
                stroke = BLUE if weekday in active_days else LINE
                work_cells.append(
                    f'<rect x="{x}" y="{y}" width="{cell_size}" height="{cell_size}" rx="1" fill="{fill}" stroke="{stroke}" stroke-width=".7"/>'
                )

        for amount, baseline, color, target in (
            (week.get("merged_prs", 0), 228, PINK, merge_bars),
            (week.get("reviews_written", 0), 289, NAVY, review_bars),
        ):
            if amount:
                height = min(int(amount), 4) * 5 + 3
                x = chart_x + index * col_step - 2
                target.append(
                    f'<rect x="{x}" y="{baseline - height}" width="19" height="{height}" rx="4" fill="{color}"/>'
                )
                target.append(
                    f'<text x="{x + 9.5}" y="{baseline - height - 5}" text-anchor="middle" class="barlabel">{int(amount)}</text>'
                )

    merged = metrics.get("merged_contributions_90d")
    reviewed = metrics.get("reviewed_by_others_90d")
    reviews_written = metrics.get("technical_reviews_90d")
    merged_text = "—" if merged is None else str(merged)
    reviewed_text = "—" if reviewed is None else str(reviewed)
    reviews_written_text = "—" if reviews_written is None else str(reviews_written)
    stamp = fmt_date(data.get("generated_at"))
    start = timeline.get("start_date")
    end = timeline.get("end_date_exclusive")
    date_span = ""
    if start and end:
        first = date.fromisoformat(start)
        last = date.fromisoformat(end) - timedelta(days=1)
        date_span = f"{first.strftime('%b %-d')} – {last.strftime('%b %-d, %Y')}"
    if weeks:
        trace_description = (
            "The 90-day calendar shows days with qualifying commits, merged pull requests, or reviews "
            "written by Rain Piao. Weekly bars show merged pull requests and other pull requests reviewed."
        )
    else:
        trace_description = "The saved snapshot predates the daily timeline, which will appear after its next refresh."
    description = (
        f"Public work trail. {trace_description} {active_text} of {total} completed weeks were active; "
        f"the current partial week is {current_text}. {merged_text} pull requests were merged, "
        f"{reviewed_text} received outside review, and {reviews_written_text} were reviewed by Rain."
    )
    trace_note = (
        '<text x="465" y="151" text-anchor="middle" class="hint">Daily contribution detail is being initialized.</text>'
        if not weeks else ""
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 360" role="img" aria-labelledby="title desc">
<title id="title">The work trail</title>
<desc id="desc">{html.escape(description)}</desc>
<style>
.title{{font:700 29px Arial,sans-serif;fill:{NAVY}}}
.subtitle{{font:15px Arial,sans-serif;fill:{MID_BLUE};letter-spacing:.5px}}
.label{{font:700 14px Arial,sans-serif;fill:{NAVY};letter-spacing:.5px}}
.hint{{font:13px Arial,sans-serif;fill:{MID_BLUE}}}
.month{{font:700 12px Arial,sans-serif;fill:{MID_BLUE};letter-spacing:.7px}}
.big{{font:700 42px Arial,sans-serif;fill:{NAVY}}}
.medium{{font:700 31px Arial,sans-serif;fill:{ROSE_TEXT}}}
.statlabel{{font:700 11px Arial,sans-serif;fill:{MID_BLUE};letter-spacing:.35px}}
.barlabel{{font:700 11px Arial,sans-serif;fill:{NAVY}}}
.micro{{font:12px Arial,sans-serif;fill:{MID_BLUE}}}
</style>
<rect x="1" y="1" width="1118" height="358" rx="22" fill="{PAPER}" stroke="{LINE}" stroke-width="2"/>
<path d="M28 12h235" stroke="{BLUE}" stroke-width="6" stroke-linecap="round"/>
<path d="M276 12h145" stroke="{PINK}" stroke-width="6" stroke-linecap="round"/>
<text x="34" y="54" class="title">THE WORK TRAIL</text>
<text x="36" y="78" class="subtitle">A 90-DAY TRACE · TRACKED PUBLIC REPOSITORIES</text>
<text x="1082" y="51" text-anchor="end" class="micro">LAST VERIFIED {html.escape(stamp.upper())}</text>
<text x="36" y="112" class="label">WORK DAYS</text>
<text x="36" y="132" class="hint">{'one square = one local day' if weeks else 'daily detail will appear'}</text>
<text x="36" y="149" class="hint">{'with qualifying activity' if weeks else 'after the next refresh'}</text>
{''.join(month_marks)}
{''.join(work_cells)}
{trace_note}
<line x1="180" y1="180" x2="744" y2="180" stroke="{LINE}" stroke-width="1"/>
<text x="36" y="211" class="label">PRs MERGED</text>
<text x="36" y="229" class="hint">one bar = weekly total</text>
<line x1="180" y1="228" x2="744" y2="228" stroke="{LINE}" stroke-width="1"/>
{''.join(merge_bars)}
<text x="36" y="272" class="label">REVIEWS WRITTEN</text>
<text x="36" y="290" class="hint">distinct PRs reviewed</text>
<line x1="180" y1="289" x2="744" y2="289" stroke="{LINE}" stroke-width="1"/>
{''.join(review_bars)}
<text x="36" y="329" class="micro">{html.escape(date_span)} · columns begin on Mondays</text>
<line x1="778" y1="82" x2="778" y2="328" stroke="{LINE}" stroke-width="2"/>
<text x="812" y="107" class="label">CURRENT READOUT</text>
<text x="811" y="160" class="big">{html.escape(active_text)}<tspan font-size="24"> / {total}</tspan></text>
<text x="814" y="183" class="statlabel">ACTIVE COMPLETE WEEKS</text>
<rect x="810" y="198" width="270" height="28" rx="14" fill="#F7E5EF"/>
<circle cx="826" cy="212" r="4" fill="{BLUE if current else PINK if current is False else LINE}"/>
<text x="839" y="216" class="micro">CURRENT PARTIAL WEEK · {html.escape(current_text.upper())}</text>
<line x1="810" y1="244" x2="1080" y2="244" stroke="{LINE}" stroke-width="1"/>
<text x="814" y="281" class="medium">{html.escape(merged_text)}</text>
<text x="906" y="281" class="medium">{html.escape(reviewed_text)}</text>
<text x="1000" y="281" class="medium">{html.escape(reviews_written_text)}</text>
<text x="814" y="301" class="statlabel">MERGED</text>
<text x="906" y="301" class="statlabel">REVIEWED</text>
<text x="1000" y="301" class="statlabel">REVIEWS</text>
<text x="814" y="320" class="micro">PRs · 90d</text>
<text x="906" y="320" class="micro">by others</text>
<text x="1000" y="320" class="micro">by Rain</text>
</svg>'''


def proof_svg(data: dict[str, Any]) -> str:
    metrics = data["metrics"]
    projects = metrics.get("verified_technical_projects", 0)
    reports = metrics.get("evaluation_reports", 0)
    stamp = fmt_date(data.get("generated_at"))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 174" role="img" aria-labelledby="title desc">
<title id="title">Inspectable evidence</title>
<desc id="desc">Two evidence checks: currently verified runnable public technical projects, {projects}; qualifying public evaluation reports, {reports}. Last successful collection: {html.escape(stamp)}.</desc>
<style>
.title{{font:700 24px Arial,sans-serif;fill:{NAVY}}}
.label{{font:700 13px Arial,sans-serif;fill:{MID_BLUE};letter-spacing:.5px}}
.value{{font:700 43px Arial,sans-serif;fill:{NAVY}}}
.note{{font:13px Arial,sans-serif;fill:{MID_BLUE}}}
</style>
<rect x="1" y="1" width="1118" height="172" rx="22" fill="#F8FBFE" stroke="{LINE}" stroke-width="2"/>
<path d="M28 12h215" stroke="{BLUE}" stroke-width="6" stroke-linecap="round"/>
<path d="M256 12h126" stroke="{PINK}" stroke-width="6" stroke-linecap="round"/>
<text x="34" y="51" class="title">WORK SOMEONE ELSE CAN CHECK</text>
<text x="36" y="76" class="note">The evidence track grows when a public result can be run and its evaluation can be inspected.</text>
<line x1="560" y1="91" x2="560" y2="146" stroke="{LINE}" stroke-width="2"/>
<circle cx="590" cy="118" r="7" fill="{BLUE}"/>
<text x="612" y="115" class="value">{projects}</text>
<text x="671" y="112" class="label">RUNNABLE PROJECTS</text>
<text x="671" y="132" class="note">public setup + verified command</text>
<circle cx="830" cy="118" r="7" fill="{PINK}"/>
<text x="852" y="115" class="value">{reports}</text>
<text x="911" y="112" class="label">EVALUATION REPORTS</text>
<text x="911" y="132" class="note">question + method + result + limits</text>
</svg>'''


def readme_block(data: dict[str, Any]) -> str:
    metrics = data["metrics"]
    active = metrics["active_weeks"]
    if data["status"] == "not_measured_yet":
        return '''<p align="center"><img src="assets/work-trail.svg" width="100%" alt="Public contribution trail; activity data is not measured yet"></p>
<p align="center"><img src="assets/proof.svg" width="100%" alt="Evidence checks for runnable projects and evaluation reports"></p>

**Tracked public work · Not measured yet** · [Definitions, scope, and evidence](docs/metrics.md)

The first successful public-data collection has not run. Empty evidence counts are separate from unmeasured activity. A failed refresh keeps the previous successful snapshot and date.'''
    start = date.fromisoformat(active["start_date"])
    active_end = date.fromisoformat(active["end_date_exclusive"]) - timedelta(days=1)
    window = f"{start.isoformat()} through {active_end.isoformat()} (eight complete local weeks)"
    pr_end = date.fromisoformat(data["window"]["end_date_exclusive"]) - timedelta(days=1)
    pr_window = f"90 complete local days through {pr_end.isoformat()}"
    generated = fmt_date(data.get("generated_at"))
    current_week = "active" if metrics["current_week"]["active"] else "not active yet"
    project_count = metrics["verified_technical_projects"]
    project_label = "project" if project_count == 1 else "projects"
    merged_count = metrics["merged_contributions_90d"]
    merged_label = "pull request" if merged_count == 1 else "pull requests"
    reviews_written = metrics.get("technical_reviews_90d")
    reviews_written_display = "not yet measured" if reviews_written is None else str(reviews_written)
    project_details = ""
    if data.get("projects"):
        links = []
        for project in data["projects"]:
            links.append(
                f"[{project['title']}]({project['url']}) "
                f"([setup and verification]({project['setup_url']}), verified {project['verified_on']})"
            )
        project_details = " · " + "; ".join(links)
    repo_links = ", ".join(
        f"[{repo}](https://github.com/{repo}/pulls)" for repo in data.get("tracked_repositories", [])
    )
    pr_evidence = f" · Pull-request records: {repo_links}" if repo_links else ""
    return f'''<p align="center"><img src="assets/work-trail.svg" width="100%" alt="Ninety-day public work trail with workday calendar, merged pull-request bars, review bars, active weeks, and collaboration counts"></p>
<p align="center"><img src="assets/proof.svg" width="100%" alt="Verified runnable public technical projects and qualifying evaluation reports"></p>

- **Cadence:** {active['count']} of 8 complete weeks · {window}; current partial week: {current_week}.
- **Completed:** {merged_count} qualifying public {merged_label} merged in the {pr_window}{pr_evidence}.
- **Reviews written:** {reviews_written_display}; a public pull request counts once even if it has several reviews.
- **Reviews received:** {metrics['reviewed_by_others_90d']} of my merged pull requests received an approval or changes-requested review from another human.
- **Evidence:** {project_count} currently verified runnable {project_label}{project_details} · {metrics['evaluation_reports']} qualifying evaluation reports.

**Tracked public work · Last verified {generated}** · [Definitions, scope, and evidence](docs/metrics.md)

Each graphic is generated from the same documented public snapshot. Small values are a starting point, not a score; private work is not included.'''


def render_outputs(data: dict[str, Any], history: dict[str, Any], readme: str) -> dict[str, str]:
    start_marker, end_marker = "<!-- METRICS-START -->", "<!-- METRICS-END -->"
    if readme.count(start_marker) != 1 or readme.count(end_marker) != 1:
        raise ValueError("README must contain exactly one pair of metrics markers")
    left = readme.index(start_marker) + len(start_marker)
    right = readme.index(end_marker)
    if right <= left:
        raise ValueError("README metrics markers are out of order")
    updated = readme[:left] + "\n" + readme_block(data) + "\n" + readme[right:]
    return {
        "assets/work-trail.svg": work_trail_svg(data),
        "assets/proof.svg": proof_svg(data),
        "data/metrics.json": json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        "data/history.json": json.dumps(history, ensure_ascii=False, indent=2) + "\n",
        "README.md": updated,
    }
