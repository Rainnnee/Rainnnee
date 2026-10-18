#!/usr/bin/env python3
"""Render accessible, self-contained SVG panels and the README metric block."""

from __future__ import annotations

import html
import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def fmt_date(value: str | None) -> str:
    if not value:
        return "Not measured yet"
    local = datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(ZoneInfo("America/Los_Angeles"))
    return local.strftime("%b %-d, %Y")


def consistency_svg(data: dict[str, Any]) -> str:
    m = data["metrics"]
    active = m["active_weeks"]
    active_count = active["count"]
    active_text = "—" if active_count is None else str(active_count)
    current_week = m.get("current_week", {}).get("active")
    current_label = "not active yet" if current_week is False else "active" if current_week else "not measured"
    weeks = active.get("weeks", [])
    cells = []
    for i in range(8):
        on = bool(weeks[i].get("active")) if i < len(weeks) else False
        x = 616 + i * 60
        fill = "#238BDF" if on else "#D8EDFA"
        stroke = "#173F70" if on else "#ADC7DA"
        cells.append(f'<rect x="{x}" y="151" width="42" height="38" rx="10" fill="{fill}" stroke="{stroke}" stroke-width="2"/>')
        cells.append(f'<text x="{x + 21}" y="216" text-anchor="middle" class="small">{i + 1}</text>')
    merged = m["merged_contributions_90d"]
    reviewed = m["reviewed_by_others_90d"]
    merged_text = "—" if merged is None else str(merged)
    reviewed_text = "—" if reviewed is None else str(reviewed)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 272" role="img" aria-labelledby="title desc">
<title id="title">Consistency and collaboration</title>
<desc id="desc">Active weeks: {html.escape(active_text)} of 8 completed weeks. Current partial week: {html.escape(current_label)}. Merged public pull requests in the last 90 days: {html.escape(merged_text)}. Merged pull requests reviewed by another human: {html.escape(reviewed_text)}.</desc>
<style>.h{{font:700 28px Arial,sans-serif;fill:#173F70}}.k{{font:16px Arial,sans-serif;fill:#315F91}}.v{{font:700 54px Arial,sans-serif;fill:#173F70}}.small{{font:14px Arial,sans-serif;fill:#315F91}}.value2{{font:700 42px Arial,sans-serif;fill:#A33E74}}</style>
<rect x="1" y="1" width="1118" height="270" rx="22" fill="#FFFAF7" stroke="#B9D2E4" stroke-width="2"/>
<path d="M28 12h310" stroke="#238BDF" stroke-width="6" stroke-linecap="round"/><path d="M352 12h145" stroke="#EFACD0" stroke-width="6" stroke-linecap="round"/>
<text x="36" y="54" class="h">Consistency and collaboration</text>
<text x="40" y="133" class="v">{html.escape(active_text)}<tspan font-size="30"> / 8</tspan></text>
<text x="42" y="167" class="k">ACTIVE WEEKS</text>
<text x="42" y="199" class="small">Complete Monday–Sunday weeks</text>
{''.join(cells)}
<line x1="595" y1="80" x2="595" y2="230" stroke="#D7E2EA" stroke-width="2"/>
<text x="664" y="119" class="value2">{html.escape(merged_text)}</text><text x="664" y="147" class="k">MERGED PRs · 90 DAYS</text>
<text x="876" y="119" class="value2">{html.escape(reviewed_text)}</text><text x="876" y="147" class="k">REVIEWED BY OTHERS</text>
<text x="664" y="198" class="small">Tracked public repositories · local time</text>
<text x="664" y="224" class="small">See the README for windows and evidence rules.</text>
<text x="42" y="249" class="small">Current partial week: {html.escape(current_label)}</text>
</svg>'''


def evidence_svg(data: dict[str, Any]) -> str:
    m = data["metrics"]
    projects = m["verified_technical_projects"]
    reports = m["evaluation_reports"]
    stamp = fmt_date(data.get("generated_at"))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1120 232" role="img" aria-labelledby="title desc">
<title id="title">Work you can inspect</title>
<desc id="desc">Currently verified runnable public technical projects: {projects}. Public evaluation reports that meet the profile criteria: {reports}. Last successful collection: {html.escape(stamp)}.</desc>
<style>.h{{font:700 28px Arial,sans-serif;fill:#173F70}}.k{{font:16px Arial,sans-serif;fill:#315F91}}.v{{font:700 58px Arial,sans-serif;fill:#173F70}}.small{{font:14px Arial,sans-serif;fill:#315F91}}</style>
<rect x="1" y="1" width="1118" height="230" rx="22" fill="#F8FBFE" stroke="#B9D2E4" stroke-width="2"/>
<path d="M28 12h250" stroke="#238BDF" stroke-width="6" stroke-linecap="round"/><path d="M292 12h170" stroke="#EFACD0" stroke-width="6" stroke-linecap="round"/>
<text x="36" y="54" class="h">Work you can inspect</text>
<text x="72" y="139" class="v">{projects}</text><text x="72" y="171" class="k">RUNNABLE TECHNICAL PROJECTS</text>
<line x1="475" y1="82" x2="475" y2="181" stroke="#D7E2EA" stroke-width="2"/>
<text x="546" y="139" class="v">{reports}</text><text x="546" y="171" class="k">EVALUATION REPORTS</text>
<text x="72" y="207" class="small">Counts require public evidence and the documented inclusion criteria.</text>
<text x="826" y="207" class="small">Last verified {html.escape(stamp)}</text>
</svg>'''


def readme_block(data: dict[str, Any]) -> str:
    m = data["metrics"]
    active = m["active_weeks"]
    if data["status"] == "not_measured_yet":
        return '''<p align="center"><img src="assets/consistency.svg" width="100%" alt="Consistency and collaboration: not measured yet"></p>
<p align="center"><img src="assets/evidence.svg" width="100%" alt="Work you can inspect: no verified runnable technical projects or qualifying reports yet"></p>

**Tracked public work · Not measured yet** · [Definitions, scope, and evidence](docs/metrics.md)

The first successful public-data collection has not run. The project and report counts are zero because the evidence ledger is empty. A failed refresh keeps the previous snapshot and date.'''
    start = date.fromisoformat(active["start_date"])
    active_end = date.fromisoformat(active["end_date_exclusive"]) - timedelta(days=1)
    window = f"{start.isoformat()} through {active_end.isoformat()} (eight complete local weeks)"
    pr_end = date.fromisoformat(data["window"]["end_date_exclusive"]) - timedelta(days=1)
    pr_window = f"last 90 complete local days through {pr_end.isoformat()}"
    generated = fmt_date(data.get("generated_at"))
    reviewed = m["reviewed_by_others_90d"]
    current_week = "active" if m["current_week"]["active"] else "not active yet"
    project_count = m["verified_technical_projects"]
    project_label = "project" if project_count == 1 else "projects"
    project_details = ""
    if data.get("projects"):
        links = []
        for project in data["projects"]:
            links.append(
                f"[{project['title']}]({project['url']}) "
                f"([setup and verification]({project['setup_url']}), verified {project['verified_on']})"
            )
        project_details = " · " + "; ".join(links)
    if data.get("tracked_repositories"):
        if len(data["tracked_repositories"]) == 1:
            repo = data["tracked_repositories"][0]
            pr_evidence = f" · [Pull-request records](https://github.com/{repo}/pulls)"
        else:
            repo_links = ", ".join(
                f"[{repo}](https://github.com/{repo}/pulls)" for repo in data["tracked_repositories"]
            )
            pr_evidence = f" · Pull-request records: {repo_links}"
    else:
        pr_evidence = ""
    return f'''<p align="center"><img src="assets/consistency.svg" width="100%" alt="Consistency and collaboration metrics"></p>
<p align="center"><img src="assets/evidence.svg" width="100%" alt="Verified public project and evaluation report counts"></p>

- **Active weeks:** {active['count']} of 8 · {window}; current partial week: {current_week}.
- **Merged contributions:** {m['merged_contributions_90d']} in the {pr_window}; {reviewed} had an approval or changes-requested review from another human before merge{pr_evidence}.
- **Runnable technical projects:** {project_count} currently verified {project_label}{project_details} · {m['evaluation_reports']} qualifying evaluation reports.

**Tracked public work · Last verified {generated}** · [Definitions, scope, and evidence](docs/metrics.md)

These custom measures cover only the listed public repositories. The README keeps its last successful snapshot when a refresh fails.'''


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
        "assets/consistency.svg": consistency_svg(data),
        "assets/evidence.svg": evidence_svg(data),
        "data/metrics.json": json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        "data/history.json": json.dumps(history, ensure_ascii=False, indent=2) + "\n",
        "README.md": updated,
    }
