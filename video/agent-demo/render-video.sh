#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCENES="${ROOT}/scenes"
OUTPUT_DIR="${ROOT}/output"
CAPTURES_DIR="${ROOT}/captures"

# Two real Codex CLI screen captures, recorded per captures/README.md's contract. Never
# committed (repo-wide .gitignore *.mp4 rule) and never substituted with an illustrative
# mockup - this script fails instead. See that README for exactly what each must show.
CONNECT_CAPTURE="${CAPTURES_DIR}/01-connect-tella.mp4"
TOOLCALLS_CAPTURE="${CAPTURES_DIR}/02-toolcalls-tella.mp4"

MP4_OUTPUT="${OUTPUT_DIR}/aip-agent-demo.mp4"
WEBP_OUTPUT="${OUTPUT_DIR}/aip-agent-demo.webp"
POSTER_OUTPUT="${OUTPUT_DIR}/aip-agent-demo-poster.png"

WIDTH=1200
HEIGHT=676

# Scene durations in seconds (sum = 39s).
D_INTRO=4
D_CONNECT=8
D_TOOLCALLS=18
D_RESULT=4
D_CTA=5

# Fade duration and, derived from it, each scene's fade-out start time (duration - fade).
# Same idiom as video/readme-demo/render-video.sh (awk, not bc - already a dependency).
FADE=0.35
FADE_OUT_INTRO=$(awk -v d="${D_INTRO}" -v f="${FADE}" 'BEGIN{printf "%.2f", d-f}')
FADE_OUT_CONNECT=$(awk -v d="${D_CONNECT}" -v f="${FADE}" 'BEGIN{printf "%.2f", d-f}')
FADE_OUT_TOOLCALLS=$(awk -v d="${D_TOOLCALLS}" -v f="${FADE}" 'BEGIN{printf "%.2f", d-f}')
FADE_OUT_RESULT=$(awk -v d="${D_RESULT}" -v f="${FADE}" 'BEGIN{printf "%.2f", d-f}')
FADE_OUT_CTA=$(awk -v d="${D_CTA}" -v f="${FADE}" 'BEGIN{printf "%.2f", d-f}')

# Placeholder panel geometry - must match PANEL_X/Y/W/H in render.py.
PANEL_X=60
PANEL_Y=198
PANEL_W=1080
PANEL_H=404

# Crop windows into the real captures, derived by extracting frames across each clip's used
# window and eyeballing where the decisive terminal content sits (same method
# video/readme-demo/render-video.sh's own DRIFT_CROP/EVIDENCE_CROP were derived by). Both
# recordings are full-1920x1080 app windows, not a tightly-framed terminal, so a full-frame
# "no crop" scale-to-fit leaves most of the panel empty. Re-derive if the captures are
# re-recorded: `ffmpeg -i <capture> -frames:v 1 <out>.png`, written under this package's
# directory, not /tmp (see README).
CONNECT_START=0.3
CONNECT_LEN=${D_CONNECT}
CONNECT_CROP="crop=1900:600:10:0"

TOOLCALLS_START=0.3
TOOLCALLS_LEN=${D_TOOLCALLS}
TOOLCALLS_CROP="crop=1920:970:0:60"

# Minimums must cover the trim window actually consumed (START + LEN), not just the output
# duration - otherwise a capture at the old, looser 8s/18s minimum would have had less footage
# available after the START offset than LEN needs, and ffmpeg would silently pad the shortfall
# with cloned frames despite this check's intent to reject exactly that. captures/README.md's
# stated minimums (9s/19s) already build in a safety margin above this exact 8.3s/18.3s
# threshold - keep both in sync if either changes.
MIN_CONNECT_SECONDS=$(awk -v s="${CONNECT_START}" -v l="${CONNECT_LEN}" 'BEGIN{printf "%.2f", s+l}')
MIN_TOOLCALLS_SECONDS=$(awk -v s="${TOOLCALLS_START}" -v l="${TOOLCALLS_LEN}" 'BEGIN{printf "%.2f", s+l}')

probe_duration() {
  local f="$1"
  if command -v ffprobe >/dev/null 2>&1; then
    ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "${f}"
  elif command -v ffmpeg.ffprobe >/dev/null 2>&1; then
    ffmpeg.ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 "${f}"
  else
    ffmpeg -i "${f}" 2>&1 | grep -oP 'Duration: \K[0-9:.]+' \
      | awk -F: '{print ($1*3600)+($2*60)+$3}'
  fi
}

check_capture() {
  local capture="$1"
  local min_seconds="$2"

  if [[ ! -f "${capture}" ]]; then
    printf 'error: required Codex CLI capture is missing: %s\n' "${capture}" >&2
    printf 'see %s/README.md for exactly what to record and how\n' "${CAPTURES_DIR}" >&2
    exit 1
  fi

  local duration
  duration="$(probe_duration "${capture}")"
  if awk -v d="${duration}" -v m="${min_seconds}" 'BEGIN { exit !(d < m) }'; then
    printf 'error: %s is %.2fs, shorter than the required %.2fs minimum\n' \
      "${capture}" "${duration}" "${min_seconds}" >&2
    printf 'ffmpeg would silently pad the shortfall with cloned frames - re-record instead\n' >&2
    exit 1
  fi
}

check_capture "${CONNECT_CAPTURE}" "${MIN_CONNECT_SECONDS}"
check_capture "${TOOLCALLS_CAPTURE}" "${MIN_TOOLCALLS_SECONDS}"

mkdir -p "${OUTPUT_DIR}"

ffmpeg -y \
  -loop 1 -t "${D_INTRO}" -i "${SCENES}/01-intro.png" \
  -loop 1 -t "${D_CONNECT}" -i "${SCENES}/02-connect.png" \
  -i "${CONNECT_CAPTURE}" \
  -loop 1 -t "${D_TOOLCALLS}" -i "${SCENES}/03-toolcalls.png" \
  -i "${TOOLCALLS_CAPTURE}" \
  -loop 1 -t "${D_RESULT}" -i "${SCENES}/04-result.png" \
  -loop 1 -t "${D_CTA}" -i "${SCENES}/05-cta.png" \
  -filter_complex "\
    [0:v]fps=30,fade=t=in:st=0:d=${FADE}:color=0x0B1020,fade=t=out:st=${FADE_OUT_INTRO}:d=${FADE}:color=0x0B1020,setpts=PTS-STARTPTS[v0];\
    [1:v]fps=30,setpts=PTS-STARTPTS[connect_bg];\
    [2:v]trim=start=${CONNECT_START}:duration=${CONNECT_LEN},setpts=PTS-STARTPTS,${CONNECT_CROP},scale=${PANEL_W}:${PANEL_H}:force_original_aspect_ratio=decrease,pad=${PANEL_W}:${PANEL_H}:(ow-iw)/2:(oh-ih)/2:color=0x050810,fps=30,tpad=stop_mode=clone:stop_duration=${D_CONNECT},trim=duration=${D_CONNECT}[connect_capture];\
    [connect_bg][connect_capture]overlay=${PANEL_X}:${PANEL_Y}:shortest=1,fade=t=in:st=0:d=${FADE}:color=0x0B1020,fade=t=out:st=${FADE_OUT_CONNECT}:d=${FADE}:color=0x0B1020[v1];\
    [3:v]fps=30,setpts=PTS-STARTPTS[toolcalls_bg];\
    [4:v]trim=start=${TOOLCALLS_START}:duration=${TOOLCALLS_LEN},setpts=PTS-STARTPTS,${TOOLCALLS_CROP},scale=${PANEL_W}:${PANEL_H}:force_original_aspect_ratio=decrease,pad=${PANEL_W}:${PANEL_H}:(ow-iw)/2:(oh-ih)/2:color=0x050810,fps=30,tpad=stop_mode=clone:stop_duration=${D_TOOLCALLS},trim=duration=${D_TOOLCALLS}[toolcalls_capture];\
    [toolcalls_bg][toolcalls_capture]overlay=${PANEL_X}:${PANEL_Y}:shortest=1,fade=t=in:st=0:d=${FADE}:color=0x0B1020,fade=t=out:st=${FADE_OUT_TOOLCALLS}:d=${FADE}:color=0x0B1020[v2];\
    [5:v]fps=30,fade=t=in:st=0:d=${FADE}:color=0x0B1020,fade=t=out:st=${FADE_OUT_RESULT}:d=${FADE}:color=0x0B1020,setpts=PTS-STARTPTS[v3];\
    [6:v]fps=30,fade=t=in:st=0:d=${FADE}:color=0x0B1020,fade=t=out:st=${FADE_OUT_CTA}:d=${FADE}:color=0x0B1020,setpts=PTS-STARTPTS[v4];\
    [v0][v1][v2][v3][v4]concat=n=5:v=1:a=0[outv]" \
  -map "[outv]" \
  -an \
  -c:v libx264 \
  -preset medium \
  -crf 18 \
  -pix_fmt yuv420p \
  -movflags +faststart \
  "${MP4_OUTPUT}"

printf 'Rendered %s\n' "${MP4_OUTPUT}"

# This package's longer runtime (39s vs. video/readme-demo's 22s) means significantly more
# frames at the same fps. ImageMagick's `policy.xml` "area" resource (commonly 256MP, a
# per-invocation ceiling regardless of any `-limit` CLI flag - a CLI limit can only lower it,
# never raise it) is a *cumulative* check across every frame in one animated-WebP build on
# some builds: at 13fps x 39s = 507 frames x 1200x676px each, that's ~411MP total, well past a
# 256MP ceiling. This failed with "cache resources exhausted" and silently wrote a
# truncated/corrupt WebP (confirmed: ffprobe reported "image data not found" on the result) -
# the fallback path only, not the native ffmpeg libwebp encoder below, which streams frames
# without holding the whole sequence in an ImageMagick pixel cache. Both branches use the same
# lower fps regardless, so the shipped WebP looks the same across environments rather than its
# smoothness depending on which encoder happened to be available at build time.
WEBP_FPS=7

if ffmpeg -hide_banner -h encoder=libwebp 2>&1 | grep -q "^Encoder libwebp"; then
  ffmpeg -y -i "${MP4_OUTPUT}" \
    -vf "fps=${WEBP_FPS},scale=${WIDTH}:${HEIGHT}:flags=lanczos" \
    -loop 0 -an -c:v libwebp -q:v 75 -preset default -compression_level 6 \
    "${WEBP_OUTPUT}"
else
  WORKDIR="$(mktemp -d "${ROOT}/.webp-frames.XXXXXX")"
  trap 'rm -rf "${WORKDIR}"' EXIT
  ffmpeg -y -i "${MP4_OUTPUT}" -vf "fps=${WEBP_FPS},scale=${WIDTH}:${HEIGHT}:flags=lanczos" \
    "${WORKDIR}/frame-%04d.png"
  convert -delay "$(awk -v f="${WEBP_FPS}" 'BEGIN{printf "%.0f", 100/f}')" -loop 0 -dispose previous \
    "${WORKDIR}"/frame-*.png -define webp:method=6 -quality 78 \
    "${WEBP_OUTPUT}"
fi

printf 'Rendered %s\n' "${WEBP_OUTPUT}"

ffmpeg -y -i "${MP4_OUTPUT}" -vf "select=eq(n\\,0)" -frames:v 1 "${POSTER_OUTPUT}"

printf 'Rendered %s\n' "${POSTER_OUTPUT}"
