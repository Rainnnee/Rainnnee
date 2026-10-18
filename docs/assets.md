# Profile artwork and metric cards

## Pixel-art banner

The banner is a deliberately coarse pixel-art view of downtown Los Angeles, framed by two differently shaped palms. A small Griffith Observatory silhouette on a distant ridge adds a restrained local landmark. The close skyline is the main subject beneath a bright cyan sky and a broad, naturally irregular cloud bank. The clouds use visibly blended cyan-blue, lilac, pink, peach, and warm-cream tones, with soft edges and no fine texture. A centered bitmap introduction reads `HI! I'M RAIN PIAO`, followed by the compact mathematical signature `Σ DATA → ML`. The landscape is averaged to a 60 × 20 grid and enlarged with nearest-neighbor sampling, keeping all sky, cloud, landmark, palm, and building pixels uniform at about 20 square pixels. The separate lettering overlay uses a smaller uniform 10-pixel bitmap grid so the greeting and name stay readable without changing the scene's coarse pixel scale. The supplied Xeuphoria artwork guides the bright palette and cloud gradients; its piano and person are not reused.

The raster master is [`assets/source/los-angeles-skyline-master.png`](../assets/source/los-angeles-skyline-master.png). [`assets/banner-static.png`](../assets/banner-static.png) is the no-motion view. [`assets/banner.gif`](../assets/banner.gif) gently shifts the cloud layer by up to two grid cells and back; the introduction and city remain still. This is an ambient animation, not a diagram of a specific model, result, or architecture used in Rain's work.

The GIF begins with the full scene visible and loops in about 2.9 seconds. Only the clouds move slightly; the introduction, skyline, landmark, and palms remain still. The static fallback is linked directly beneath the banner for a no-motion view.

Run `python3 scripts/render_banner.py` to regenerate the static and animated outputs from the raster master. The script averages the source into the 60 × 20 scene grid, retains enough colors for the cloud gradients, adds the compact bitmap introduction and math signature, shifts only cloud cells in a slow loop while protecting the skyline and palm silhouettes, and scales every scene cell with nearest-neighbor sampling. Keep the source artwork, exported dimensions, animation timing, and file size in sync when changing the banner.

## Metric cards

The consistency and evidence cards are original SVG data graphics with text equivalents in the README. Their palette uses warm white `#FFFAF7`, pale sky `#D8EDFA`, blue `#238BDF`, pink `#EFACD0`, navy `#173F70`, cyan `#59DEFF`, and lilac `#DFD3FF`. Metric cards are simple technical diagrams, not banner artwork. Navy carries small labels, contrast remains readable, and color is never the only way to interpret a value.
