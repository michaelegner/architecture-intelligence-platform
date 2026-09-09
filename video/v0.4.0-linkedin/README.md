# AIP v0.4.0 — Silent LinkedIn Release Video

This production package implements the approved 60-second, silent, 4:5 LinkedIn storyboard. The
release renderer requires authentic Tella footage for the drift and evidence scenes and will fail
instead of silently substituting illustrative terminal mockups.

## Deliverables

- `aip-v0.4.0-linkedin-silent.mp4` — final release master, created only when both captures exist
- `aip-v0.4.0-linkedin-silent-mockup-draft.mp4` — superseded first visual draft
- `storyboard.png` — contact sheet for reviewing the complete narrative
- `scenes/*.png` — Canva-ready scene cards
- `scenes/*.svg` — editable vector sources
- `render.py` — reproducible scene renderer

## Required Tella captures

Create these exact files before rendering:

- `captures/05-drift-tella.mp4` — at least 12 seconds
- `captures/06-evidence-tella.mp4` — at least 11 seconds

Record from a clean run of `examples/runtime-demo/mcp-demo.sh`. Scene 5 must show the real
`tools/call` request and the returned `LegacyPricingService` claim qualified `OBSERVED_ONLY`.
Scene 6 must show the real `get_evidence` call and the OpenTelemetry provenance returned at the
same snapshot.

In Tella:

1. Use a dark terminal, at least 20 px terminal text, and keep the relevant output in the central
   84% of the frame so the portrait crop does not remove it.
2. Disable microphone, camera, system audio, click sounds, and decorative backgrounds.
3. Export 1920×1080 at 30 fps with no audio track.
4. Hold the final result long enough to meet each minimum duration; the renderer trims clips to
   exactly 12 and 11 seconds.

The generated scene 5–6 PNGs are capture backplates for the storyboard, not substitutes accepted
by the final renderer.

## Rebuild the scene cards

```bash
python3 video/v0.4.0-linkedin/render.py
```

## Rebuild the final MP4

```bash
bash video/v0.4.0-linkedin/render-video.sh
```

The final MP4 is assembled from the eight scene cards with subtle motion and short dark fades.
Its scene timing is `4 / 5 / 10 / 7 / 12 / 11 / 6 / 5` seconds.
