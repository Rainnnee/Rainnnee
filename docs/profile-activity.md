# GitHub activity

The README uses three cards: a public activity overview, the current year's contribution calendar, and public repository languages. All three share the same typography, spacing, and banner-inspired cyan, blue, pink, and lavender accents on neutral backgrounds. Each has a light and dark version selected using GitHub's supported `<picture>` theme markup.

## Automatic refresh

The workflow requests a refresh **hourly**, at 17 minutes past the hour, and can also run manually. It refreshes on changes to the README, generator, tests, or workflow on `main` and review branches under `profile/`. Recurring schedules run only on the repository's default branch. The hourly schedule starts applying to a review revision after it is merged into `main`.

The overview displays the last successful collection time, including its timezone. These are automatically refreshed images, not a streaming dashboard: GitHub may delay scheduled jobs, source indexing, or image cache updates. The README links to the workflow's run history so freshness is easy to check.

## Sources and scopes

- **Contributions:** GitHub's displayed contribution calendar for the current calendar year. This follows GitHub's counting rules and any private activity totals the user has chosen to show publicly. It is not a raw commit count.
- **Commits:** GitHub's public commit search for `author:Rainnnee`, across all time. Search indexing, default-branch attribution, and email association affect what GitHub returns.
- **Pull requests and issues:** public items authored by Rain, across all time, including open and closed items.
- **Repositories:** the account's public repository count.
- **Language percentages:** aggregate bytes from the languages endpoint for public, owned, non-fork repositories. This describes repository contents, not proficiency. Front-end experience and ML tools are listed independently in the README.
- **Current streak:** consecutive active days ending today or yesterday, using the current year's calendar.
- **Longest streak and active days:** calculated within the current calendar year through the refresh date. A streak crossing January 1 is limited to the current year's displayed data.
- **Activity rank:** the all-commits rank formula from GitHub Readme Stats, using public commits, authored PRs/issues, stars on owned non-fork repositories, followers, and distinct public PRs reviewed by Rain (excluding self-authored PRs). The reviewed-PR count differs from upstream's review-event count. The rank is an activity indicator, not a skill or code-quality grade. Attribution and the MIT license are in [third-party notices](third-party-notices.md).

The collector reads only public endpoints. GitHub Actions supplies its standard repository token to raise API rate limits; no personal access token or third-party stats hosting is required. Tokens are never saved in the snapshots.

## Validation and failure behavior

The calendar parser verifies one entry for every day, readable counts, and agreement between daily counts and the year total. API searches must report complete results. All data is collected and every card rendered before the output files are replaced. A collection or rendering failure leaves the previous successful snapshot in place and fails the workflow visibly.

Snapshots: `data/profile-activity.json` and `data/github-stats.json`. Images: `assets/github-{overview,activity,languages}-{light,dark}.svg`. `assets/github-activity.svg` remains a light-theme compatibility copy.

Run locally:

```sh
python3 -m unittest discover -s tests -p test_profile_activity.py
python3 scripts/update_profile_activity.py
```

## Design references

- [Awesome GitHub Profile README](https://github.com/abhisheknaiidu/awesome-github-profile-readme#tools): activity and language visualization ideas.
- [GitHub Readme Stats](https://github.com/anuraghazra/github-readme-stats): activity rank formula.
- [GitHub theme-aware image guidance](https://github.blog/developer-skills/github/how-to-make-your-images-in-markdown-on-github-adjust-for-dark-mode-and-light-mode/).
