# AIP — Evergreen README Demo

This production package builds the short (22 second, silent, 1200×676 landscape) animation
embedded inline at the top of the repository's `README.md`. Unlike
[`video/v0.4.0-linkedin/`](../v0.4.0-linkedin/), it carries no version number, release badge, or
scene counter — it is meant to stay accurate across releases without being re-cut.

It tells one story: a real `get_architecture_drift` call surfaces an undocumented dependency, and
a real `get_evidence` call traces that same claim to the OpenTelemetry observation that proves it.

## Deliverables

- `output/aip-readme-demo.mp4` — silent H.264 master, source quality
- `output/aip-readme-demo.webp` — animated WebP, this is what `README.md` actually embeds
- `storyboard.png` — 2×2 contact sheet for reviewing all four scenes at once
- `scenes/*.png` — rendered scene backplates
- `scenes/*.svg` — editable vector sources
- `render.py` / `render-video.sh` — reproducible renderers

## Why the WebP, not the MP4, is what's embedded in `README.md`

GitHub only autoplays `<video>`-tag content when the file was uploaded through its own web-UI
drag-and-drop asset pipeline (a `user-attachments` CDN URL). A `<video src="...">` (or any tag)
pointing at an ordinary committed repo path does **not** autoplay inline. A plain markdown image
reference to an **animated WebP** (`![alt](path.webp)`) does autoplay and loop, because that's
ordinary browser `<img>` animated-image behavior — the same mechanism that makes animated GIFs
work in READMEs, unrelated to GitHub's video-tag sanitizer. So `README.md` references
`video/readme-demo/output/aip-readme-demo.webp` directly with `![]()` syntax — never a `<video>`
or `<picture>` tag. The MP4 stays in the repo as a higher-quality master (useful if anyone wants
to manually drag-and-drop it into a GitHub PR/release comment for a true HTML5 player), but it is
not itself embeddable from a committed path.

## Reused inputs — do not duplicate or re-record

Both real MCP-call screen captures already exist in the sibling LinkedIn package and are
referenced from there directly (`../v0.4.0-linkedin/captures/`):

- `05-drift-tella.mp4` (8.5s) — real `get_architecture_drift` response: `order-service`'s call to
  `LegacyPricingService` qualified `OBSERVED_ONLY` — a dependency seen in traffic, declared
  nowhere.
- `06-evidence-tella.mp4` (8.7s) — real `get_evidence` response resolving that same claim's
  `evidence_refs` to its OpenTelemetry provenance, at the same graph snapshot.

Both were recorded under the capture contract documented in
[`../v0.4.0-linkedin/captures/README.md`](../v0.4.0-linkedin/captures/README.md): real terminal
output from a clean `examples/runtime-demo/mcp-demo.sh` run, no mockups. If either file is ever
re-recorded, re-check the crop constants described below before re-rendering.

## Palette

Reuses the exact constants already established in
[`../v0.4.0-linkedin/render.py`](../v0.4.0-linkedin/render.py) — not the separate, older palette
baked into `images/pipeline-*.svg` (different hex values, no teal):

| Constant | Hex | Use |
|---|---|---|
| `BACKGROUND` | `#0B1020` | page background |
| `PANEL` / `PANEL_LIGHT` | `#111A2E` / `#16233D` | card fills |
| `TEXT` / `MUTED` | `#F8FAFC` / `#94A3B8` | primary / secondary text |
| `BLUE` | `#38BDF8` | declared |
| `TEAL` | `#2DD4BF` | evidence-backed |
| `AMBER` | `#F59E0B` | observed-only / drift |
| `GREEN`, `PURPLE`, `RED` | `#22C55E`, `#8B5CF6`, `#FB7185` | unused here, kept for parity |

## Rebuild

```bash
python3 video/readme-demo/render.py
bash video/readme-demo/render-video.sh
```

`render.py` needs only the Python standard library plus the `convert`/`montage` CLIs
(ImageMagick). `render-video.sh` needs `ffmpeg`. Neither needs a PyPI or npm dependency.

Two portability notes, both already handled in `render-video.sh`:

- **`ffprobe` may not be on `PATH`** (only `ffmpeg.ffprobe`, a snap alias, in some environments).
  The duration probe tries `ffprobe`, then `ffmpeg.ffprobe`, then falls back to parsing
  `ffmpeg -i`'s stderr.
- **`ffmpeg` may be built without a `libwebp` encoder.** The script checks for it and, if absent,
  falls back to extracting frames and building the animated WebP with ImageMagick's `convert`
  (which has full animated-WebP support independent of ffmpeg's own encoder list).

Both the MP4 encode and the WebP frame-extraction fallback write into directories under this
package (`output/`, a `mktemp -d` inside `${ROOT}`) rather than the system `/tmp` — a sandboxed
`ffmpeg` build may not have write access outside the project tree.

## Scene timing

`4 / 7 / 7 / 4` seconds = 22s total: architecture mismatch → drift result (real capture) →
evidence drill-down (real capture) → CTA. Transitions are 0.35s fades through the background
color (`#0B1020`), matching the sibling package's convention — short enough to read as a cut,
long enough not to flash, and because both the CTA's fade-out and scene 1's fade-in pass through
the same solid color, the WebP's loop point (final frame back to first frame) reads as a soft
dissolve rather than a hard cut, with no separately authored loop-blend needed.

The capture crop windows (`DRIFT_CROP`/`EVIDENCE_CROP` and the `*_START`/`*_LEN` constants near
the top of `render-video.sh`) were picked by extracting and eyeballing frames from both clips —
both are static (no scroll) for their full duration, so the exact window only needs to sit safely
inside the dark terminal box. If the captures are re-recorded, re-derive these by extracting a
frame or two (e.g. `ffmpeg -i <capture> -frames:v 1 <out>.png`, written under this package's
directory, not `/tmp`, for the same sandboxed-ffmpeg reason above) and sampling pixel colors at
the box edges before touching the constants.

## Acceptance criteria

- MP4 under 3MB, WebP under 5MB (hard ceiling 8MB) — both currently well under (~0.4MB / ~1.3MB)
- No audio track on either output
- ~22s total, 1200×676, no scaling artifacts
- First meaningful result (the `OBSERVED_ONLY` edge in scene 1) visible well before t=5s
- Text legible at 1200×676 and still legible scaled to ~375px mobile width
- `video/v0.4.0-linkedin/` (its script, README, output, and captures) stays untouched by any
  change to this package
