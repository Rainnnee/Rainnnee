#!/usr/bin/env python3
"""Collect scoped, public GitHub activity and atomically refresh profile cards."""

from __future__ import annotations

import json
import os
import re
import sys
import tempfile
import time
from datetime import date, datetime, time as day_time, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from render_metrics import render_outputs

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.github.com"
LOCAL_TZ = ZoneInfo("America/Los_Angeles")
OWNER = "Rainnnee"
USER_AGENT = "Rainnnee-profile-metrics/1.0"
MAX_API_CALLS = 52
MAX_SEARCH_RESULTS = 1000
IGNORED_STATES = {"COMMENTED", "PENDING", "DISMISSED"}


class CollectionError(RuntimeError):
    pass


class GitHub:
    def __init__(self, token: str | None = None) -> None:
        self.calls = 0
        self.last_search_at = 0.0
        self.token = token

    def get(self, url: str, *, search: bool = False) -> tuple[Any, dict[str, str]]:
        if self.calls >= MAX_API_CALLS:
            raise CollectionError(f"API request budget exceeded ({MAX_API_CALLS}); no files were changed")
        if search and self.last_search_at:
            delay = 6.1 - (time.monotonic() - self.last_search_at)
            if delay > 0:
                time.sleep(delay)
        self.calls += 1
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": USER_AGENT,
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=25) as response:
                body = response.read()
                response_headers = {k.lower(): v for k, v in response.headers.items()}
        except HTTPError as exc:
            if exc.code in (403, 429):
                remaining = exc.headers.get("X-RateLimit-Remaining", "unknown")
                reset = exc.headers.get("X-RateLimit-Reset", "unknown")
                raise CollectionError(f"GitHub rate limit or access limit (HTTP {exc.code}, remaining {remaining}, reset {reset})") from exc
            raise CollectionError(f"GitHub API returned HTTP {exc.code} for a public data request") from exc
        except (URLError, TimeoutError) as exc:
            raise CollectionError(f"Could not reach the public GitHub API: {exc.reason if isinstance(exc, URLError) else exc}") from exc
        if search:
            self.last_search_at = time.monotonic()
        try:
            return json.loads(body), response_headers
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CollectionError("GitHub API returned malformed JSON") from exc

    def pages(self, url: str, *, search: bool = False) -> list[Any]:
        result: list[Any] = []
        next_url: str | None = url
        while next_url:
            payload, headers = self.get(next_url, search=search)
            if search:
                if payload.get("incomplete_results"):
                    raise CollectionError("GitHub search returned an incomplete result set")
                total = int(payload.get("total_count", 0))
                if total > MAX_SEARCH_RESULTS:
                    raise CollectionError(f"GitHub search found {total} results; refusing an incomplete snapshot")
                result.extend(payload.get("items", []))
            elif isinstance(payload, list):
                result.extend(payload)
            else:
                raise CollectionError("Expected a paginated GitHub API list")
            link = headers.get("link", "")
            next_url = None
            for part in link.split(","):
                match = re.match(r"\s*<([^>]+)>;\s*rel=\"next\"", part)
                if match:
                    next_url = match.group(1)
                    break
        return result

    def search_prs(self, repo: str, qualifier: str, start: date, end_exclusive: date) -> list[dict[str, Any]]:
        end_inclusive = end_exclusive - timedelta(days=1)
        query = f"repo:{repo} is:pr is:merged {qualifier} merged:{start.isoformat()}..{end_inclusive.isoformat()}"
        url = f"{API}/search/issues?{urlencode({'q': query, 'per_page': 100})}"
        return self.pages(url, search=True)


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def local_day(value: str | None) -> date | None:
    parsed = parse_dt(value)
    return parsed.astimezone(LOCAL_TZ).date() if parsed else None


def within(value: str | None, start: date, end_exclusive: date) -> bool:
    day = local_day(value)
    return bool(day and start <= day < end_exclusive)


def local_midnight_utc(day: date) -> str:
    return datetime.combine(day, day_time.min, tzinfo=LOCAL_TZ).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def is_meaningful_commit(files: list[dict[str, Any]], repo_config: dict[str, Any], message: str) -> bool:
    if not files:
        return False
    prefixes = tuple(str(x).strip("/") + "/" for x in repo_config.get("excluded_path_prefixes", []))
    lockfiles = set(repo_config.get("dependency_only_filenames", []))
    paths = [str(item.get("filename", "")).replace("\\", "/").lstrip("./") for item in files]
    if not any(paths):
        return False
    remaining = [p for p in paths if p and not any(p.startswith(prefix) for prefix in prefixes)]
    if not remaining or all(Path(p).name in lockfiles for p in remaining):
        return False
    lower_message = message.lower()
    if any(term in lower_message for term in ("bot:", "[bot]", "automated dependency")):
        return False
    return True


def fetch_activity(client: GitHub, repos: list[str], repo_config: dict[str, Any], today: date) -> tuple[dict[str, Any], dict[str, Any]]:
    week_start = today - timedelta(days=today.weekday())
    weeks_start = week_start - timedelta(weeks=8)
    pr_start = today - timedelta(days=90)
    event_days: set[date] = set()
    merged_total = 0
    reviewed_by_others = 0
    for repo in repos:
        info, _ = client.get(f"{API}/repos/{repo}")
        if info.get("visibility") != "public" or info.get("private"):
            raise CollectionError(f"{repo} is not public; refusing to read it")
        branch = info.get("default_branch")
        if not branch:
            raise CollectionError(f"{repo} has no verified default branch")

        start_utc = local_midnight_utc(pr_start)
        end_utc = local_midnight_utc(today)
        commit_url = f"{API}/repos/{repo}/commits?{urlencode({'author': OWNER, 'sha': branch, 'since': start_utc, 'until': end_utc, 'per_page': 100})}"
        commits = client.pages(commit_url)
        for summary in commits:
            if not isinstance(summary, dict) or not summary.get("sha"):
                raise CollectionError(f"Malformed commit record in {repo}")
            details, _ = client.get(f"{API}/repos/{repo}/commits/{summary['sha']}")
            if len(details.get("parents", [])) > 1:
                continue
            author = (details.get("author") or {}).get("login", "")
            if author.casefold() != OWNER.casefold():
                continue
            commit = details.get("commit") or {}
            authored = (commit.get("author") or {}).get("date")
            day = local_day(authored)
            if day is None or not pr_start <= day < today:
                continue
            if not is_meaningful_commit(details.get("files", []), repo_config, commit.get("message", "")):
                continue
            if day >= weeks_start:
                event_days.add(day)

        # Search is limited to the recent merged window; matching PRs are fetched
        # once, then their review records establish both collaboration measures.
        authored_items = client.search_prs(repo, f"author:{OWNER}", pr_start, today)
        reviewed_items = client.search_prs(repo, f"reviewed-by:{OWNER}", pr_start, today)
        numbers: dict[int, dict[str, Any]] = {}
        for item in authored_items + reviewed_items:
            number = item.get("number")
            if number is not None:
                numbers[int(number)] = item
        for number in sorted(numbers):
            pull, _ = client.get(f"{API}/repos/{repo}/pulls/{number}")
            if not within(pull.get("merged_at"), pr_start, today):
                continue
            pr_day = local_day(pull.get("merged_at"))
            user = (pull.get("user") or {}).get("login", "")
            own_pr = user.casefold() == OWNER.casefold()
            if own_pr:
                merged_total += 1
                if pr_day and pr_day >= weeks_start:
                    event_days.add(pr_day)
            reviews_url = f"{API}/repos/{repo}/pulls/{number}/reviews?per_page=100"
            reviews = client.pages(reviews_url)
            if not isinstance(reviews, list):
                raise CollectionError(f"Malformed review list for {repo}#{number}")
            qualifying_reviewers = set()
            own_review_days = set()
            for review in reviews:
                state = str(review.get("state", "")).upper()
                reviewer = (review.get("user") or {}).get("login", "")
                submitted = review.get("submitted_at")
                submitted_at = parse_dt(submitted)
                merged_at = parse_dt(pull.get("merged_at"))
                if state in IGNORED_STATES or not submitted_at:
                    continue
                if state not in {"APPROVED", "CHANGES_REQUESTED"}:
                    continue
                if own_pr and reviewer.casefold() != OWNER.casefold() and not (reviewer.endswith("[bot]") or reviewer.casefold().endswith("-bot")) and merged_at and submitted_at < merged_at:
                    qualifying_reviewers.add(reviewer.casefold())
                if reviewer.casefold() == OWNER.casefold() and pr_start <= submitted_at.astimezone(LOCAL_TZ).date() < today:
                    own_review_days.add(submitted_at.astimezone(LOCAL_TZ).date())
            if own_pr and qualifying_reviewers:
                reviewed_by_others += 1
            for day in own_review_days:
                if day >= weeks_start:
                    event_days.add(day)

    weeks = []
    active_count = 0
    for i in range(8):
        start = weeks_start + timedelta(weeks=i)
        end = start + timedelta(days=7)
        active = any(start <= d < end for d in event_days)
        active_count += int(active)
        weeks.append({
            "start_date": start.isoformat(),
            "end_date_inclusive": (end - timedelta(days=1)).isoformat(),
            "label": start.strftime("%b %-d"),
            "active": active,
        })
    partial_week_active = any(week_start <= d < today for d in event_days)
    activity = {
        "active_weeks": {
            "count": active_count,
            "total": 8,
            "start_date": weeks_start.isoformat(),
            "end_date_exclusive": week_start.isoformat(),
            "weeks": weeks,
        },
        "current_week": {
            "active": partial_week_active,
            "start_date": week_start.isoformat(),
            "as_of_date": today.isoformat(),
        },
        "merged_contributions_90d": merged_total,
        "reviewed_by_others_90d": reviewed_by_others,
    }
    window = {"start_date": pr_start.isoformat(), "end_date_exclusive": today.isoformat(), "timezone": "America/Los_Angeles"}
    return activity, window


def verified_evidence(path: Path, today: date) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    try:
        ledger = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CollectionError(f"Could not read evidence ledger: {exc}") from exc
    if ledger.get("schema_version") != 1 or not isinstance(ledger.get("projects"), list) or not isinstance(ledger.get("reports"), list):
        raise CollectionError("Evidence ledger schema is invalid")
    projects = []
    project_ids: set[str] = set()
    for item in ledger["projects"]:
        required = ("id", "title", "url", "visibility", "revision", "role", "setup_url", "run_command", "data_source", "verification_scope", "expected_output", "verified_on", "verification_result")
        if any(key not in item for key in required):
            raise CollectionError("A project ledger item is missing a required field")
        project_id = item["id"]
        if not isinstance(project_id, str) or not project_id.strip():
            raise CollectionError("A project ledger item has an invalid ID")
        if project_id in project_ids:
            raise CollectionError(f"Duplicate project ID {project_id!r}; keep one current verification record per project")
        project_ids.add(project_id)
        if item["visibility"] != "public":
            continue
        verified_on = date.fromisoformat(item["verified_on"])
        age = (today - verified_on).days
        if item["verification_result"] == "passed" and 0 <= age <= 90:
            projects.append({
                "id": item["id"],
                "title": item["title"],
                "url": item["url"],
                "revision": item["revision"],
                "setup_url": item["setup_url"],
                "role": item["role"],
                "verification_scope": item["verification_scope"],
                "verified_on": item["verified_on"],
            })
    reports_by_id: dict[str, dict[str, Any]] = {}
    for item in ledger["reports"]:
        required = ("id", "title", "project_id", "url", "visibility", "question", "protocol_url", "result_interpretation", "limitations", "evidence_url", "result_date", "review_status", "status")
        if any(key not in item for key in required):
            raise CollectionError("A report ledger item is missing a required field")
        report_id = item["id"]
        if not isinstance(report_id, str) or not report_id.strip():
            raise CollectionError("A report ledger item has an invalid ID")
        evidence_fields = ("question", "protocol_url", "result_interpretation", "limitations", "evidence_url", "result_date", "review_status")
        if item["visibility"] == "public" and item["status"] == "published":
            if any(not isinstance(item[field], str) or not item[field].strip() for field in evidence_fields):
                raise CollectionError(f"Published report {report_id!r} is missing required evidence")
            reports_by_id.setdefault(report_id, {"id": report_id, "title": item["title"], "url": item["url"], "evidence_url": item["evidence_url"]})
    return projects, list(reports_by_id.values())


def atomic_refresh(outputs: dict[str, str]) -> None:
    import shutil

    stage = Path(tempfile.mkdtemp(prefix=".metrics-stage-", dir=ROOT))
    try:
        for relative, content in outputs.items():
            target = stage / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("w", encoding="utf-8", newline="\n") as handle:
                handle.write(content)
        for relative in outputs:
            target = ROOT / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            os.replace(stage / relative, target)
    finally:
        shutil.rmtree(stage, ignore_errors=True)


def main() -> int:
    try:
        config = json.loads((ROOT / "data/tracked-repositories.json").read_text(encoding="utf-8"))
        if config.get("schema_version") != 1 or config.get("owner", "").casefold() != OWNER.casefold():
            raise CollectionError("Tracked repository list schema or owner is invalid")
        repos = config.get("repositories")
        if not isinstance(repos, list) or not repos:
            raise CollectionError("At least one explicitly tracked public repository is required")
        repo_names = []
        for entry in repos:
            name = entry.get("full_name", "")
            if name.count("/") != 1 or name.split("/", 1)[0].casefold() != OWNER.casefold():
                raise CollectionError(f"Invalid tracked repository entry: {name!r}")
            if name.casefold() == f"{OWNER}/{OWNER}".casefold():
                raise CollectionError("The profile repository must never be included in its own metrics")
            repo_names.append(name)
        today = datetime.now(LOCAL_TZ).date()
        # Actions provides a short-lived, repository-scoped token. Locally the
        # collector can still run without one, but public requests then use the
        # lower unauthenticated rate limit.
        client = GitHub(os.environ.get("GITHUB_TOKEN"))
        activity, window = fetch_activity(client, repo_names, config, today)
        projects, reports = verified_evidence(ROOT / "data/evidence.json", today)
        generated = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        data = {
            "schema_version": 1,
            "status": "measured",
            "generated_at": generated,
            "timezone": "America/Los_Angeles",
            "definitions_version": 2,
            "tracked_repositories": repo_names,
            "window": window,
            "metrics": {
                **activity,
                "verified_technical_projects": len(projects),
                "evaluation_reports": len(reports),
            },
            "projects": projects,
            "reports": reports,
            "collector": {"api_requests": client.calls, "source": "GitHub public REST API"},
        }
        history_path = ROOT / "data/history.json"
        if history_path.exists():
            try:
                history = json.loads(history_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as exc:
                raise CollectionError("Existing history file is malformed; preserving all outputs") from exc
        else:
            history = {"schema_version": 1, "snapshots": []}
        if history.get("schema_version") != 1 or not isinstance(history.get("snapshots"), list):
            raise CollectionError("Existing history file has an unsupported schema")
        snapshot = {"generated_at": generated, "definitions_version": data["definitions_version"], "window": window, "metrics": data["metrics"], "tracked_repositories": repo_names}
        history["snapshots"].append(snapshot)
        history["snapshots"] = history["snapshots"][-1040:]
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        outputs = render_outputs(data, history, readme)
        atomic_refresh(outputs)
        print(f"Updated public metrics from {len(repo_names)} tracked repository/repositories using {client.calls} API requests.")
        print(f"Active weeks: {activity['active_weeks']['count']}/8; merged PRs: {activity['merged_contributions_90d']}; reviewed by others: {activity['reviewed_by_others_90d']}; verified runnable technical projects: {len(projects)}; reports: {len(reports)}.")
        return 0
    except (CollectionError, OSError, ValueError, TypeError, KeyError) as exc:
        print(f"Metrics refresh failed; last successful outputs were preserved: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
