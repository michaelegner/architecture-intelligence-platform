# AIP — Agent-in-Action Demo

**Status: pipeline built, not yet rendered.** The two required real captures
(`captures/01-connect-tella.mp4`, `captures/02-toolcalls-tella.mp4`) have not been recorded yet, so
`output/aip-agent-demo.webp` does not exist and `README.md` does not embed it yet — embedding a
reference to a file that doesn't exist would be a broken image on GitHub. Once the real captures are
recorded (see "Required Codex CLI captures" below) and `render-video.sh` produces the final WebP, a
follow-up change adds the actual `README.md` embed.

This production package builds a short (~39 second, silent, 1200×676 landscape) animation intended
for `README.md`'s "Connect AIP to Your Coding Agent" section. Like
[`video/readme-demo/`](../readme-demo/), it carries no version number, release badge, or scene
counter — it demonstrates a durable capability (a coding agent using AIP's tools on its own), not a
release-specific claim, so it should not need re-cutting on the next release.

It tells a different story than the top-of-README hero animation: that one shows *what* AIP
returns (a direct `get_architecture_drift`/`get_evidence` call pair). This one shows *how* a real
coding agent gets there — connecting, asking one plain-language question, and autonomously calling
both tools itself with no manual per-call direction.

**Scope: Codex CLI only.** Not a multi-client montage — showing every qualified client in one
animation would clutter the narrative. The closing scene points to the
[compatibility matrix](../../docs/release-validation/v0.4.2-client-qualification.md) for
Claude Code, Cursor, and VS Code instead.

## Deliverables

Once the real captures exist and `render-video.sh` has been run, everything below will be committed
to the repo **except** the MP4 and the raw captures, which are gitignored (repo-wide `*.mp4` rule)
as regenerable/source build artifacts, exactly like `video/v0.4.0-linkedin/`'s and
`video/readme-demo/`'s own packages. Currently committed: `render.py`, `render-video.sh`, this
README, `captures/README.md`, `scenes/*.svg`/`*.png`, and `storyboard.png`. Not yet committed
(pipeline exists, awaiting the real captures): `output/aip-agent-demo.webp`,
`output/aip-agent-demo-poster.png`.

- `output/aip-agent-demo.mp4` — silent H.264 master, source quality, **not committed** — rebuild
  locally with `render-video.sh` if you need it
- `output/aip-agent-demo.webp` — animated WebP — **will be committed** once rendered; this is what
  `README.md` will embed
- `output/aip-agent-demo-poster.png` — **will be committed** once rendered, a static first-frame
  poster for slow connections
- `storyboard.png` — committed, 3×2 contact sheet for reviewing all five scenes at once
- `scenes/*.png` — committed, rendered scene backplates
- `scenes/*.svg` — committed, editable vector sources
- `render.py` / `render-video.sh` — committed, reproducible renderers
- `captures/*.mp4` — **not committed** — the real Codex CLI screen recordings (see below)

## Why the WebP, not the MP4, will be what's embedded in `README.md`

Same reasoning as `video/readme-demo/README.md`: GitHub only autoplays `<video>`-tag content
uploaded through its own web-UI drag-and-drop pipeline, not a `<video src="...">` pointing at an
ordinary committed repo path. A plain markdown image reference to an **animated WebP**
(`![alt](path.webp)`) autoplays and loops via ordinary browser `<img>` animated-image behavior — the
same mechanism animated GIFs use. So once rendered, `README.md` will reference
`video/agent-demo/output/aip-agent-demo.webp` directly with `![]()` syntax, never a `<video>` tag.

## Required Codex CLI captures

**The renderer requires real screen recordings and fails instead of substituting an illustrative
terminal mockup** — this repo's established discipline for this kind of asset
(`video/v0.4.0-linkedin/render-video.sh` does the same).

Create these exact files before rendering:

- `captures/01-connect-tella.mp4` — at least 8 seconds
- `captures/02-toolcalls-tella.mp4` — at least 18 seconds

Record from a clean `examples/runtime-demo/mcp-demo.sh --serve`, in one continuous Codex CLI session
split into two clips:

1. **Clip 1 (`01-connect-tella.mp4`):** run `codex mcp add aip --url http://localhost:8000/mcp`,
   confirm it connects, then submit README.md's existing stable prompt verbatim — reuse that exact
   wording, don't invent a new prompt variant:

   > Use AIP to find architecture drift for service:order-service in the demo environment between
   > 2026-08-26T00:00:00Z and 2026-08-27T00:00:00Z. For every finding, explain its qualification and
   > resolve its evidence using the same snapshot. Do not infer facts AIP does not establish.

2. **Clip 2 (`02-toolcalls-tella.mp4`):** continue the same session. It must show Codex
   autonomously calling `get_architecture_drift` then `get_evidence` as distinct, visible tool-call
   events in its own terminal UI — no manual per-call direction — ending on its final synthesized
   answer naming `LegacyPricingService`/`OBSERVED_ONLY` and citing the OpenTelemetry evidence. (A
   real `codex exec --json` run against this exact prompt was used to confirm this is genuinely the
   current tool-call sequence and answer shape before authoring the surrounding scene copy — Codex
   calls `get_architecture_drift` once, then one `get_evidence` call resolving all three cited
   references, then reports both findings.)

In Tella (same specs as `video/v0.4.0-linkedin/README.md`'s established contract):

1. Use a dark terminal, at least 20 px terminal text, and keep the relevant output in the central
   84% of the frame so cropping/scaling does not remove it.
2. Disable microphone, camera, system audio, click sounds, and decorative backgrounds.
3. Export 1920×1080 at 30 fps with no audio track.
4. Hold the final result long enough to meet each minimum duration; the renderer trims clips to
   exactly 8 and 18 seconds.

## Palette

Reuses the exact constants already established in
[`../readme-demo/render.py`](../readme-demo/render.py) (itself reused from
`../v0.4.0-linkedin/render.py`) — not the separate, older palette baked into
`images/pipeline-*.svg`:

| Constant | Hex | Use |
|---|---|---|
| `BACKGROUND` | `#0B1020` | page background |
| `PANEL` / `PANEL_LIGHT` | `#111A2E` / `#16233D` | card fills |
| `TEXT` / `MUTED` | `#F8FAFC` / `#94A3B8` | primary / secondary text |
| `BLUE` | `#38BDF8` | declared / the agent itself |
| `TEAL` | `#2DD4BF` | evidence-backed / autonomous action |
| `AMBER` | `#F59E0B` | observed-only / drift |
| `GREEN`, `PURPLE`, `RED` | `#22C55E`, `#8B5CF6`, `#FB7185` | unused here, kept for parity |

## Rebuild

```bash
python3 video/agent-demo/render.py
bash video/agent-demo/render-video.sh
```

`render.py` needs only the Python standard library plus the `convert`/`montage` CLIs
(ImageMagick) and runs without the real captures present — it only produces the scene backplates
and storyboard. `render-video.sh` needs `ffmpeg` and `awk`, and requires both real captures.
Neither needs a PyPI or npm dependency.

Same portability handling as `video/readme-demo/render-video.sh`:

- **`ffprobe` may not be on `PATH`** (only `ffmpeg.ffprobe`, a snap alias, in some environments).
  The duration probe tries `ffprobe`, then `ffmpeg.ffprobe`, then falls back to parsing
  `ffmpeg -i`'s stderr.
- **`ffmpeg` may be built without a `libwebp` encoder.** The script checks for it and, if absent,
  falls back to extracting frames and building the animated WebP with ImageMagick's `convert`.

Both the MP4 encode and the WebP frame-extraction fallback write into directories under this
package (`output/`, a `mktemp -d` inside `${ROOT}`) rather than the system `/tmp`.

## Scene timing

`4 / 8 / 18 / 4 / 5` seconds = 39s total: intro (agent → AIP) → connect-and-ask (real capture) →
autonomous tool calls (real capture) → result → CTA. Transitions are 0.35s fades through the
background color (`#0B1020`), matching `video/readme-demo/`'s convention.

**Crop windows are untuned placeholders.** `render-video.sh`'s `CONNECT_CROP`/`TOOLCALLS_CROP`
currently default to "no crop, just scale to fit" because no real footage exists yet. Once the two
captures above are recorded, re-derive these the same way `video/readme-demo/README.md` documents:
extract a frame or two (e.g. `ffmpeg -i <capture> -frames:v 1 <out>.png`, written under this
package's directory, not `/tmp`), eyeball where the decisive terminal content sits, and crop tightly
to it so the composited text reads at a legible size instead of shrinking to a sliver of the panel.

## Acceptance criteria

- MP4 under 3MB, WebP under 5MB (hard ceiling 8MB) — same budget as `video/readme-demo/`
- No audio track on any output
- ~39s total, 1200×676, no scaling artifacts
- The autonomous tool-call moment (scene 3) reads clearly as the agent acting on its own, not a
  manually-driven sequence
- Text legible at 1200×676 and still legible scaled to ~375px mobile width
- `video/readme-demo/` and `video/v0.4.0-linkedin/` (their scripts, READMEs, outputs, and captures)
  stay untouched by any change to this package
