from __future__ import annotations

import html
import subprocess
from pathlib import Path

WIDTH = 1200
HEIGHT = 676  # even, libx264/yuv420p requires it; matches the readme-demo package's framing

# Palette reused verbatim from video/readme-demo/render.py (itself reused from
# video/v0.4.0-linkedin/render.py) -- do not diverge from these values, they are the
# established AIP brand system for this kind of asset.
BACKGROUND = "#0B1020"
PANEL = "#111A2E"
PANEL_LIGHT = "#16233D"
TEXT = "#F8FAFC"
MUTED = "#94A3B8"
BLUE = "#38BDF8"
TEAL = "#2DD4BF"
GREEN = "#22C55E"
AMBER = "#F59E0B"
PURPLE = "#8B5CF6"
RED = "#FB7185"

# Placeholder panel geometry -- render-video.sh composites the real Tella captures into
# this exact rectangle on scenes 02 and 03. Keep these two definitions in sync. Deliberately
# PANEL_H=404, not readme-demo/render.py's PANEL_H=405: an odd height is invalid for yuv420p
# (chroma planes are subsampled by 2 in both dimensions), and real captures decode as yuv420p
# - discovered when compositing genuine Tella footage into this panel produced "Padded
# dimensions cannot be smaller than input dimensions" from ffmpeg's pad filter on every frame
# past the first. Confirmed via isolated ffmpeg tests: the exact same scale+pad chain succeeds
# at PANEL_H=404 and fails at 405, regardless of crop/scale details.
PANEL_X = 60
PANEL_Y = 198
PANEL_W = 1080
PANEL_H = 404

ROOT = Path(__file__).resolve().parent
SCENES_DIR = ROOT / "scenes"


def text(
    value: str,
    x: int,
    y: int,
    size: int,
    *,
    fill: str = TEXT,
    weight: int = 400,
    anchor: str = "start",
    family: str = "DejaVu Sans",
    spacing: int = 0,
) -> str:
    escaped = html.escape(value)
    return (
        f'<text x="{x}" y="{y}" fill="{fill}" font-family="{family}" '
        f'font-size="{size}" font-weight="{weight}" text-anchor="{anchor}" '
        f'letter-spacing="{spacing}">{escaped}</text>'
    )


def rect(
    x: int,
    y: int,
    width: int,
    height: int,
    *,
    fill: str = PANEL,
    stroke: str = "#263653",
    radius: int = 24,
    stroke_width: int = 2,
    opacity: float = 1,
) -> str:
    return (
        f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}" opacity="{opacity}"/>'
    )


def line(x1: int, y1: int, x2: int, y2: int, *, stroke: str, width: int = 4) -> str:
    return (
        f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{stroke}" '
        f'stroke-width="{width}" stroke-linecap="round" marker-end="url(#arrow)"/>'
    )


def badge(
    value: str, x: int, y: int, width: int, color: str, *, height: int = 60, size: int = 26
) -> str:
    return "".join(
        [
            rect(x, y, width, height, fill=f"{color}18", stroke=color, radius=height // 2),
            text(
                value,
                x + width // 2,
                y + height // 2 + int(size * 0.35),
                size,
                fill=color,
                weight=700,
                anchor="middle",
            ),
        ]
    )


def logo(x: int, y: int, scale: float = 1) -> str:
    first = f"{x},{y + int(74 * scale)} {x + int(46 * scale)},{y} {x + int(76 * scale)},{y + int(42 * scale)}"
    second = f"{x + int(52 * scale)},{y + int(74 * scale)} {x + int(88 * scale)},{y + int(20 * scale)} {x + int(128 * scale)},{y + int(74 * scale)}"
    return (
        f'<polygon points="{first}" fill="url(#logoGradient)"/>'
        f'<polygon points="{second}" fill="url(#logoGradient2)"/>'
    )


def node(cx: int, cy: int, r: int, label: str, color: str) -> str:
    return "".join(
        [
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{color}" opacity=".85"/>',
            f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="{color}" stroke-width="2"/>',
            text(
                label,
                cx,
                cy + r + 30,
                20,
                fill=TEXT,
                weight=700,
                anchor="middle",
                family="DejaVu Sans Mono",
            ),
        ]
    )


def base(section: str) -> list[str]:
    # Evergreen header: no version badge, no scene-number counter, no progress bar -- same
    # framing choice as video/readme-demo/render.py's own base(), for the same reason: this
    # demonstrates a durable capability (an agent using AIP's tools), not a release-specific
    # claim, so it should not need re-cutting on the next release.
    return [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">',
        "<defs>",
        '<linearGradient id="logoGradient" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#38BDF8"/><stop offset="1" stop-color="#2563EB"/></linearGradient>',
        '<linearGradient id="logoGradient2" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#2563EB"/><stop offset="1" stop-color="#4F46E5"/></linearGradient>',
        '<radialGradient id="halo"><stop stop-color="#2DD4BF" stop-opacity=".16"/><stop offset="1" stop-color="#2DD4BF" stop-opacity="0"/></radialGradient>',
        '<pattern id="grid" width="42" height="42" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="1.4" fill="#31415D" opacity=".5"/></pattern>',
        '<marker id="arrow" markerWidth="10" markerHeight="10" refX="8" refY="3" orient="auto"><path d="M0,0 L0,6 L9,3 z" fill="#38BDF8"/></marker>',
        "</defs>",
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="{BACKGROUND}"/>',
        f'<rect width="{WIDTH}" height="{HEIGHT}" fill="url(#grid)"/>',
        '<ellipse cx="1020" cy="90" rx="260" ry="260" fill="url(#halo)"/>',
        logo(48, 38, 0.42),
        text("AIP", 112, 66, 26, weight=700),
        text(section.upper(), 1152, 62, 16, fill=MUTED, weight=700, anchor="end", spacing=3),
        '<rect x="48" y="86" width="1104" height="2" fill="#263653"/>',
        text(
            "github.com/michaelegner/architecture-intelligence-platform",
            48,
            651,
            15,
            fill=MUTED,
            family="DejaVu Sans Mono",
        ),
    ]


def finish(parts: list[str]) -> str:
    return "\n".join([*parts, "</svg>"])


def scene_intro() -> str:
    parts = base("Agent in action")
    parts.extend(
        [
            text("A real coding agent.", 64, 190, 42, weight=700),
            text("Using AIP autonomously.", 64, 238, 42, fill=TEAL, weight=700),
            node(280, 420, 40, "Codex CLI", BLUE),
            line(340, 420, 620, 420, stroke=TEAL, width=4),
            node(700, 420, 44, "AIP /mcp", TEAL),
            text(
                "no manual per-call direction",
                480,
                380,
                18,
                fill=MUTED,
                anchor="middle",
                family="DejaVu Sans Mono",
            ),
        ]
    )
    return finish(parts)


def capture_scene(section: str, title: str, subtitle: str, accent: str) -> str:
    parts = base(section)
    parts.extend(
        [
            text(title, 64, 132, 38, weight=700),
            text(subtitle, 64, 172, 19, fill=MUTED, family="DejaVu Sans Mono"),
            rect(40, 185, 1120, 430, fill="#080D18", stroke="#334155", radius=20),
            rect(PANEL_X, PANEL_Y, PANEL_W, PANEL_H, fill="#050810", stroke=accent, radius=12),
        ]
    )
    return finish(parts)


def scene_connect() -> str:
    return capture_scene(
        "Connect and ask",
        "Codex CLI connects and asks.",
        "codex mcp add aip · architecture-drift prompt",
        BLUE,
    )


def scene_toolcalls() -> str:
    return capture_scene(
        "Autonomous tool calls",
        "The agent calls the tools itself.",
        "get_architecture_drift -> get_evidence -- live, autonomous",
        TEAL,
    )


def scene_result() -> str:
    parts = base("Result")
    parts.extend(
        [
            text("Found it. Traced it.", 64, 170, 42, weight=700),
            text("No guessed facts.", 64, 218, 42, fill=TEAL, weight=700),
            node(300, 420, 34, "order-service", BLUE),
            line(334, 420, 660, 420, stroke=AMBER, width=4),
            node(720, 420, 34, "LegacyPricingService", AMBER),
            badge("OBSERVED_ONLY", 560, 495, 280, AMBER),
            badge("EVIDENCE: OPENTELEMETRY", 830, 250, 340, TEAL, height=52, size=20),
        ]
    )
    return finish(parts)


def scene_cta() -> str:
    parts = base("Get started")
    parts.extend(
        [
            text("Evidence-qualified context.", 600, 260, 44, weight=700, anchor="middle"),
            text("Same snapshot. Read-only tools.", 600, 316, 34, fill=MUTED, anchor="middle"),
            rect(280, 400, 640, 86, fill="#102B35", stroke=TEAL, radius=43, stroke_width=3),
            text(
                "SEE THE QUALIFIED CLIENTS",
                600,
                452,
                24,
                fill=TEAL,
                weight=700,
                anchor="middle",
                spacing=1,
            ),
            text(
                "docs/release-validation/v0.4.2-client-qualification.md",
                600,
                510,
                17,
                fill=MUTED,
                anchor="middle",
                family="DejaVu Sans Mono",
            ),
        ]
    )
    return finish(parts)


SCENES = [
    ("01-intro", 4, scene_intro),
    ("02-connect", 8, scene_connect),
    ("03-toolcalls", 18, scene_toolcalls),
    ("04-result", 4, scene_result),
    ("05-cta", 5, scene_cta),
]


def render_scene(name: str, builder) -> None:
    svg_path = SCENES_DIR / f"{name}.svg"
    png_path = SCENES_DIR / f"{name}.png"
    svg_path.write_text(builder(), encoding="utf-8")
    subprocess.run(
        ["convert", "-background", "none", str(svg_path), str(png_path)],
        check=True,
    )


def render_storyboard() -> None:
    png_paths = [str(SCENES_DIR / f"{name}.png") for name, _, _ in SCENES]
    subprocess.run(
        [
            "montage",
            *png_paths,
            "-thumbnail",
            "360x203",
            "-tile",
            "3x2",
            "-geometry",
            "+12+12",
            str(ROOT / "storyboard.png"),
        ],
        check=True,
    )


def main() -> None:
    SCENES_DIR.mkdir(parents=True, exist_ok=True)
    for name, _, builder in SCENES:
        render_scene(name, builder)
    render_storyboard()
    print("Rendered evergreen agent-demo scenes and storyboard.")


if __name__ == "__main__":
    main()
