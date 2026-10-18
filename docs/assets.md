# Profile artwork and data graphics

## Pixel-art banner

The banner is a deliberately coarse pixel-art view of downtown Los Angeles, framed by two differently shaped palms. A small Griffith Observatory silhouette on a distant ridge adds a restrained local landmark. The close skyline is the main subject beneath a bright cyan sky and a broad, naturally irregular cloud bank. The clouds use visibly blended cyan-blue, lilac, pink, peach, and warm-cream tones, with soft edges and no fine texture. A centered bitmap introduction reads HI! I'M RAIN PIAO, followed by the compact mathematical signature Σ DATA → ML. The landscape is averaged to a 60 × 20 grid and enlarged with nearest-neighbor sampling, keeping all sky, cloud, landmark, palm, and building pixels uniform at about 20 square pixels. The separate lettering overlay uses a smaller uniform 10-pixel bitmap grid so the greeting and name stay readable without changing the scene's coarse pixel scale. The supplied Xeuphoria artwork guides the bright palette and cloud gradients; its piano and person are not reused.

The raster master is assets/source/los-angeles-skyline-master.png. assets/banner-static.png is the no-motion view. assets/banner.gif gently shifts the cloud layer by up to two grid cells and back; the introduction and city remain still. This is an ambient animation, not a diagram of a specific model, result, or architecture used in Rain's work.

The GIF begins with the full scene visible and loops in about 2.9 seconds. Only the clouds move slightly; the introduction, skyline, landmark, and palms remain still. The static fallback is linked directly beneath the banner for a no-motion view.

Run python3 scripts/render_banner.py to regenerate the static and animated outputs from the raster master. The script averages the source into the 60 × 20 scene grid, retains enough colors for the cloud gradients, adds the compact bitmap introduction and math signature, shifts only cloud cells in a slow loop while protecting the skyline and palm silhouettes, and scales every scene cell with nearest-neighbor sampling. Keep the source artwork, exported dimensions, animation timing, and file size in sync when changing the banner.

## Contribution dashboard

The README's two coordinated SVG panels use a warm-white surface, fine pale-blue borders, navy labels, bright-blue work marks, and pink merge accents. The first panel, assets/work-trail.svg, is a 90-day contribution trace: one seven-cell column per Monday-starting week, with each filled day representing at least one qualifying commit, merge, or review written. Two aligned bar lanes show weekly merged pull requests and distinct pull requests reviewed. A readout beside the timeline reports active complete weeks, the current partial week, merges, reviews received on merged work, and reviews written. The second panel, assets/proof.svg, counts currently runnable public projects and qualifying evaluation reports.

Both graphics are generated from the same validated data snapshot and accompanied by normal Markdown text that repeats the values, windows, links, and evidence rules. A zero is a real measured zero; an API failure preserves the last successful snapshot. The timeline is a presence visualization, not a score, hours estimate, or quality ranking. Labels and the text summary ensure color is not the only way to interpret a value.
