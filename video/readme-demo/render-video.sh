#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCENES="${ROOT}/scenes"
OUTPUT_DIR="${ROOT}/output"

# The two real MCP-call screen captures live in the sibling LinkedIn video package and
# are reused here by reference -- never duplicated, never re-recorded. See that
# package's captures/README.md for the recording contract both clips were made under.
CAPTURES_DIR="${ROOT}/../v0.4.0-linkedin/captures"
DRIFT_CAPTURE="${CAPTURES_DIR}/05-drift-tella.mp4"
EVIDENCE_CAPTURE="${CAPTURES_DIR}/06-evidence-tella.mp4"

MP4_OUTPUT="${OUTPUT_DIR}/aip-readme-demo.mp4"
WEBP_OUTPUT="${OUTPUT_DIR}/aip-readme-demo.webp"

WIDTH=1200
HEIGHT=676

# Scene durations in seconds (sum = 22s).
D_MISMATCH=4
D_DRIFT=7
D_EVIDENCE=7
D_CTA=4

# Placeholder panel geometry -- must match PANEL_X/Y/W/H in render.py.
PANEL_X=60
PANEL_Y=198
PANEL_W=1080
PANEL_H=405

# Crop windows into the real captures. Picked by extracting and eyeballing frames from
# both clips: the terminal content is static for the full recording (no scroll to time
# around), so these crop the decisive JSON block tightly rather than the whole 1700px-tall
# terminal box -- a full-box crop scaled down into the panel above made the composited
# text too small to read. Both crops deliberately drop the less essential header line
# ("==> Asking ..." / "==> Resolving ...") and, for evidence, the third (least central)
# evidence entry, to keep the remaining text as large as possible. Re-derive these by
# extracting a frame (e.g. `ffmpeg -i <capture> -frames:v 1 <out>.png`, written under this
# package's directory, not /tmp -- see README) and cropping candidates to eyeball if the
# captures are ever re-recorded.
DRIFT_START=0.3
DRIFT_LEN=7.0
DRIFT_CROP="crop=1300:480:110:452"

EVIDENCE_START=0.3
EVIDENCE_LEN=7.0
EVIDENCE_CROP="crop=1300:410:110:210"

# Both real captures are ~8.5s/8.7s long; keep the minimum comfortably below that
# instead of copying video/v0.4.0-linkedin/render-video.sh's 12s/11s, which were never
# actually met by these files.
MIN_CAPTURE_SECONDS=7

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
    printf 'error: required Tella capture is missing: %s\n' "${capture}" >&2
    printf 'see %s/README.md for where it is supposed to come from\n' "${ROOT}" >&2
    exit 1
  fi

  local duration
  duration="$(probe_duration "${capture}")"
  if awk -v d="${duration}" -v m="${min_seconds}" 'BEGIN { exit !(d < m) }'; then
    printf 'error: %s is %.2fs, shorter than the required %ds minimum\n' \
      "${capture}" "${duration}" "${min_seconds}" >&2
    printf 'ffmpeg would silently pad the shortfall with cloned frames - re-record instead\n' >&2
    exit 1
  fi
}

check_capture "${DRIFT_CAPTURE}" "${MIN_CAPTURE_SECONDS}"
check_capture "${EVIDENCE_CAPTURE}" "${MIN_CAPTURE_SECONDS}"

mkdir -p "${OUTPUT_DIR}"

ffmpeg -y \
  -loop 1 -t "${D_MISMATCH}" -i "${SCENES}/01-mismatch.png" \
  -loop 1 -t "${D_DRIFT}" -i "${SCENES}/02-drift.png" \
  -i "${DRIFT_CAPTURE}" \
  -loop 1 -t "${D_EVIDENCE}" -i "${SCENES}/03-evidence.png" \
  -i "${EVIDENCE_CAPTURE}" \
  -loop 1 -t "${D_CTA}" -i "${SCENES}/04-cta.png" \
  -filter_complex "\
    [0:v]fps=30,fade=t=in:st=0:d=0.35:color=0x0B1020,fade=t=out:st=$(echo "${D_MISMATCH}-0.35" | bc):d=0.35:color=0x0B1020,setpts=PTS-STARTPTS[v0];\
    [1:v]fps=30,setpts=PTS-STARTPTS[drift_bg];\
    [2:v]trim=start=${DRIFT_START}:duration=${DRIFT_LEN},setpts=PTS-STARTPTS,${DRIFT_CROP},scale=${PANEL_W}:${PANEL_H}:force_original_aspect_ratio=decrease,pad=${PANEL_W}:${PANEL_H}:(ow-iw)/2:(oh-ih)/2:color=0x050810,fps=30,tpad=stop_mode=clone:stop_duration=${D_DRIFT},trim=duration=${D_DRIFT}[drift_capture];\
    [drift_bg][drift_capture]overlay=${PANEL_X}:${PANEL_Y}:shortest=1,fade=t=in:st=0:d=0.35:color=0x0B1020,fade=t=out:st=$(echo "${D_DRIFT}-0.35" | bc):d=0.35:color=0x0B1020[v1];\
    [3:v]fps=30,setpts=PTS-STARTPTS[evidence_bg];\
    [4:v]trim=start=${EVIDENCE_START}:duration=${EVIDENCE_LEN},setpts=PTS-STARTPTS,${EVIDENCE_CROP},scale=${PANEL_W}:${PANEL_H}:force_original_aspect_ratio=decrease,pad=${PANEL_W}:${PANEL_H}:(ow-iw)/2:(oh-ih)/2:color=0x050810,fps=30,tpad=stop_mode=clone:stop_duration=${D_EVIDENCE},trim=duration=${D_EVIDENCE}[evidence_capture];\
    [evidence_bg][evidence_capture]overlay=${PANEL_X}:${PANEL_Y}:shortest=1,fade=t=in:st=0:d=0.35:color=0x0B1020,fade=t=out:st=$(echo "${D_EVIDENCE}-0.35" | bc):d=0.35:color=0x0B1020[v2];\
    [5:v]fps=30,fade=t=in:st=0:d=0.35:color=0x0B1020,fade=t=out:st=$(echo "${D_CTA}-0.35" | bc):d=0.35:color=0x0B1020,setpts=PTS-STARTPTS[v3];\
    [v0][v1][v2][v3]concat=n=4:v=1:a=0[outv]" \
  -map "[outv]" \
  -an \
  -c:v libx264 \
  -preset medium \
  -crf 18 \
  -pix_fmt yuv420p \
  -movflags +faststart \
  "${MP4_OUTPUT}"

printf 'Rendered %s\n' "${MP4_OUTPUT}"

if ffmpeg -hide_banner -h encoder=libwebp 2>&1 | grep -q "^Encoder libwebp"; then
  ffmpeg -y -i "${MP4_OUTPUT}" \
    -vf "fps=13,scale=${WIDTH}:${HEIGHT}:flags=lanczos" \
    -loop 0 -an -c:v libwebp -q:v 75 -preset default -compression_level 6 \
    "${WEBP_OUTPUT}"
else
  WORKDIR="$(mktemp -d "${ROOT}/.webp-frames.XXXXXX")"
  trap 'rm -rf "${WORKDIR}"' EXIT
  ffmpeg -y -i "${MP4_OUTPUT}" -vf "fps=13,scale=${WIDTH}:${HEIGHT}:flags=lanczos" \
    "${WORKDIR}/frame-%04d.png"
  convert -delay "$(awk 'BEGIN{printf "%.0f", 100/13}')" -loop 0 -dispose previous \
    "${WORKDIR}"/frame-*.png -define webp:method=6 -quality 78 \
    "${WEBP_OUTPUT}"
fi

printf 'Rendered %s\n' "${WEBP_OUTPUT}"
