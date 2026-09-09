#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCENES="${ROOT}/scenes"
CAPTURES="${ROOT}/captures"
DRIFT_CAPTURE="${CAPTURES}/05-drift-tella.mp4"
EVIDENCE_CAPTURE="${CAPTURES}/06-evidence-tella.mp4"
OUTPUT="${ROOT}/aip-v0.4.0-linkedin-silent.mp4"

for capture in "${DRIFT_CAPTURE}" "${EVIDENCE_CAPTURE}"; do
  if [[ ! -f "${capture}" ]]; then
    printf 'error: required Tella capture is missing: %s\n' "${capture}" >&2
    printf 'see %s/README.md for the recording contract\n' "${ROOT}" >&2
    exit 1
  fi
done

ffmpeg -y \
  -loop 1 -t 4 -i "${SCENES}/01-release.png" \
  -loop 1 -t 5 -i "${SCENES}/02-problem.png" \
  -loop 1 -t 10 -i "${SCENES}/03-pipeline.png" \
  -loop 1 -t 7 -i "${SCENES}/04-tools.png" \
  -loop 1 -t 12 -i "${SCENES}/05-drift.png" \
  -i "${DRIFT_CAPTURE}" \
  -loop 1 -t 11 -i "${SCENES}/06-evidence.png" \
  -i "${EVIDENCE_CAPTURE}" \
  -loop 1 -t 6 -i "${SCENES}/07-value.png" \
  -loop 1 -t 5 -i "${SCENES}/08-cta.png" \
  -filter_complex "\
    [0:v]scale=1110:1388,crop=1080:1350:x='15+4*sin(t*0.70)':y='19+4*cos(t*0.50)',fps=30,fade=t=in:st=0:d=0.35:color=0x0B1020,fade=t=out:st=3.65:d=0.35:color=0x0B1020,setpts=PTS-STARTPTS[v0];\
    [1:v]scale=1110:1388,crop=1080:1350:x='15-4*sin(t*0.55)':y='19+4*cos(t*0.45)',fps=30,fade=t=in:st=0:d=0.35:color=0x0B1020,fade=t=out:st=4.65:d=0.35:color=0x0B1020,setpts=PTS-STARTPTS[v1];\
    [2:v]scale=1110:1388,crop=1080:1350:x='15+4*sin(t*0.42)':y='19-4*cos(t*0.38)',fps=30,fade=t=in:st=0:d=0.35:color=0x0B1020,fade=t=out:st=9.65:d=0.35:color=0x0B1020,setpts=PTS-STARTPTS[v2];\
    [3:v]scale=1110:1388,crop=1080:1350:x='15-4*sin(t*0.40)':y='19+4*cos(t*0.36)',fps=30,fade=t=in:st=0:d=0.35:color=0x0B1020,fade=t=out:st=6.65:d=0.35:color=0x0B1020,setpts=PTS-STARTPTS[v3];\
    [4:v]fps=30,setpts=PTS-STARTPTS[drift_bg];\
    [5:v]setpts=PTS-STARTPTS,scale=896:600:force_original_aspect_ratio=decrease,pad=896:600:(ow-iw)/2:(oh-ih)/2:color=0x050814,fps=30,tpad=stop_mode=clone:stop_duration=12,trim=duration=12[drift_capture];\
    [drift_bg][drift_capture]overlay=92:440:shortest=1,fade=t=in:st=0:d=0.35:color=0x0B1020,fade=t=out:st=11.65:d=0.35:color=0x0B1020[v4];\
    [6:v]fps=30,setpts=PTS-STARTPTS[evidence_bg];\
    [7:v]setpts=PTS-STARTPTS,scale=896:600:force_original_aspect_ratio=decrease,pad=896:600:(ow-iw)/2:(oh-ih)/2:color=0x050814,fps=30,tpad=stop_mode=clone:stop_duration=11,trim=duration=11[evidence_capture];\
    [evidence_bg][evidence_capture]overlay=92:440:shortest=1,fade=t=in:st=0:d=0.35:color=0x0B1020,fade=t=out:st=10.65:d=0.35:color=0x0B1020[v5];\
    [8:v]scale=1110:1388,crop=1080:1350:x='15+4*sin(t*0.42)':y='19-4*cos(t*0.38)',fps=30,fade=t=in:st=0:d=0.35:color=0x0B1020,fade=t=out:st=5.65:d=0.35:color=0x0B1020,setpts=PTS-STARTPTS[v6];\
    [9:v]scale=1110:1388,crop=1080:1350:x='15-4*sin(t*0.55)':y='19+4*cos(t*0.45)',fps=30,fade=t=in:st=0:d=0.35:color=0x0B1020,fade=t=out:st=4.65:d=0.35:color=0x0B1020,setpts=PTS-STARTPTS[v7];\
    [v0][v1][v2][v3][v4][v5][v6][v7]concat=n=8:v=1:a=0[outv]" \
  -map "[outv]" \
  -an \
  -c:v libx264 \
  -preset medium \
  -crf 18 \
  -pix_fmt yuv420p \
  -movflags +faststart \
  "${OUTPUT}"

printf 'Rendered %s\n' "${OUTPUT}"
