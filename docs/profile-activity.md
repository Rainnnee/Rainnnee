# Profile activity card

The card is a compact, visual version of the contribution calendar GitHub already shows on Rain's public profile. The day squares preserve GitHub's activity levels, the large number repeats its year total, and the short bars summarize each month. The image updates weekly so the page can show a growing record without relying on star or follower counts.

## Data and limits

`scripts/update_profile_activity.py` reads the public HTML contribution calendar for the current year. It uses only the displayed yearly total, daily counts, and intensity levels. It verifies that every calendar day is present and that the daily counts add up to GitHub's stated total before writing either output. It does not inspect private repositories, store API responses, or score activity as ability.

The script writes `data/profile-activity.json` and `assets/github-activity.svg` atomically. If GitHub changes the page format, the script fails without replacing the previous card. The `Refresh profile activity card` workflow can be run manually from Actions and also runs weekly; its repository token only has permission to commit the generated files.

The profile's languages and project descriptions are curated separately because the code mix in two public repositories is not a reliable measurement of everything Rain knows or is learning.
