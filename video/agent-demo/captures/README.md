# Codex CLI capture inputs

Place the two required silent exports here:

- `01-connect-tella.mp4`: 1920×1080, 30 fps, at least 9 seconds (the renderer trims a 0.3s lead-in
  and needs 8s of output after that, so it rejects anything under 8.3s — record comfortably above
  that, not exactly at the boundary)
- `02-toolcalls-tella.mp4`: 1920×1080, 30 fps, at least 19 seconds (same 0.3s lead-in trim, needs
  18s of output after that — rejects anything under 18.3s)

The renderer deliberately fails when either file is absent. See the parent README for the exact
content and framing contract.
