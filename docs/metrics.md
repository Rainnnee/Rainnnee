# Metrics: definitions, scope, and evidence

These measures describe a small, explicitly scoped public record. They are not GitHub-wide totals, grades, or proxies for ability. The source list is [data/tracked-repositories.json](../data/tracked-repositories.json); the profile repository is excluded so the dashboard cannot count its own generated updates. Private repositories and private activity are never collected.

## Current snapshot

The latest successful values live in [data/metrics.json](../data/metrics.json); [data/history.json](../data/history.json) keeps dated snapshots. The current definitions are version 3. Version 1 counted a locally served personal site as a reproducible project, which did not demonstrate runnable technical work; its project count is retained only as a historical record and is not comparable with later definitions. Version 2 established the stricter evidence baseline. Version 3 adds the dated work trail and a count of distinct public pull requests reviewed by Rain.

The work trail covers the 90 complete local days before refresh, with weeks aligned Monday through Sunday in America/Los_Angeles. Its day grid marks each local date containing at least one qualifying commit, merged pull request, or substantive review written by Rain. Its two bar lanes show weekly totals for merged pull requests and distinct pull requests reviewed. The separate active-weeks count uses the latest eight complete weeks; the current partial week is labeled separately. The page shows the date of the last successful collection. An API or validation failure preserves the previous snapshot and graphics rather than replacing them with zeros.

## Measures

| Label | Definition |
| --- | --- |
| Active weeks | Of the last eight completed local weeks, weeks containing a qualifying commit, merged pull request, or substantive review by Rain on a tracked public repository. This is a presence measure, not hours or quality. |
| Merged contributions | Pull requests authored by Rain and merged into a tracked repository during the 90-day window. A repository and pull request number count once. Closed, unmerged requests are excluded. |
| Reviewed by others | Merged contributions that received an approval or changes-requested review from a different human account before merge. Bot and self reviews are excluded. This is evidence of a review process, not proof of correctness or authorship. |
| Reviews written | Distinct tracked public pull requests authored by someone else where Rain submitted at least one approval or changes-requested review during the 90-day window. Comments, pending or dismissed reviews, bot accounts, and self-reviews are excluded. This records review participation, not review quality. |
| Runnable technical projects | Distinct public technical projects with a recent passed verification under the rules below. A personal site, repository scaffold, or project description alone does not qualify. |
| Evaluation reports | Distinct public reports with a question, protocol, interpreted result, limitations, and linked evidence. |

Qualifying commits are authored by Rain, reachable on a tracked repository's default branch, and change meaningful code, tests, technical documentation, or analysis. Merge-only commits are excluded. Commits consisting only of dependency lockfiles or paths under vendor, third_party, node_modules, dist, or build are excluded. Git metadata cannot establish intellectual substance, so exclusions and evidence should be reviewed periodically. A workday cell is a presence marker, not a commit-volume or time-spent measure.

All timestamps are converted to America/Los_Angeles before assignment to a local date. Windows are start-inclusive and end-exclusive. Commit activity uses the commit author date, pull requests use merged_at, and reviews use submitted_at. Counts may change after a rebase changes default-branch reachability or after repository scope changes.

## Evidence rules

A project counts only when its public record names a revision, gives working environment instructions, identifies permitted data or a small substitute, provides a runnable command or notebook, states the expected output, and records what was rerun and when. The artifact must contain a technical implementation, analysis, or experiment; a static personal website and a README-only starter are excluded. A CPU smoke example may qualify when its scope is clear, but does not prove full training reproduction. Verifications expire after 90 days; the historical record remains in the ledger.

An evaluation report states a specific question, a comparison or baseline where appropriate, dataset or simulation, split or protocol, result interpretation, and limitations. A chart or screenshot by itself does not qualify. Several plots or runs for one coherent report count as one report.

The public evidence ledger is [data/evidence.json](../data/evidence.json). It currently has no entries: none of the tracked public repositories yet meets the runnable-project check, and no public evaluation report meets the criteria. Private work may be summarized in the profile only at a high level and is never exported into this ledger or metric counts. Add entries only after checking that the artifact is public and the rules are met. Keep private datasets, collaborator details, unpublished research, API response dumps, and credentials out of this repository.

## Refresh and failures

The Update public profile metrics workflow runs weekly and can be triggered manually from the Actions tab. It uses the repository-scoped GitHub token for authenticated public API reads and to commit the generated dashboard graphics and snapshots. It does not require a personal access token.

The collector validates pagination, repository visibility, API responses, time windows, and ledger entries before writing. If collection, rendering, or validation fails, it exits unsuccessfully and leaves the last successful snapshot intact. Automated refresh commits are excluded from tracked activity.

GitHub may delay scheduled runs and may disable them after prolonged repository inactivity. Use the manual workflow for an immediate refresh. See [GitHub's schedule event documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).
