from __future__ import annotations

import html
import subprocess
from pathlib import Path

WIDTH = 1200
HEIGHT = 676  # even, libx264/yuv420p requires it; 1200x676 is ~16:9

# Palette reused verbatim from video/v0.4.0-linkedin/render.py -- do not diverge from
# these values, they are the established AIP brand system for this kind of asset.
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
# this exact rectangle on scenes 02 and 03. Keep these two definitions in sync. Sized as
# large as the layout allows (and cropped tight in render-video.sh) so the composited
# terminal text reads at a legible size instead of shrinking to a sliver of the frame.
PANEL_X = 60
PANEL_Y = 198
PANEL_W = 1080
PANEL_H = 405

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
    # Evergreen header: no version badge, no scene-number counter, no progress bar --
    # deliberately unlike video/v0.4.0-linkedin/render.py's base(scene_number, section).
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


def scene_mismatch() -> str:
    parts = base("Architecture mismatch")
    parts.extend(
        [
            text("Declared architecture.", 64, 170, 42, weight=700),
            text("Reality doesn't match.", 64, 218, 42, fill=AMBER, weight=700),
            line(284, 400, 560, 310, stroke=BLUE, width=4),
            line(284, 400, 560, 490, stroke=BLUE, width=4),
            line(284, 400, 900, 400, stroke=AMBER, width=4),
            node(250, 400, 34, "order-service", BLUE),
            node(620, 300, 28, "product-service", BLUE),
            node(620, 490, 28, "payment-service", BLUE),
            node(950, 400, 28, "LegacyPricingService", AMBER),
            badge("OBSERVED_ONLY", 810, 495, 280, AMBER),
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


def scene_drift() -> str:
    return capture_scene(
        "Drift result",
        "Undocumented dependency found.",
        "get_architecture_drift — live MCP response",
        AMBER,
    )


def scene_evidence() -> str:
    return capture_scene(
        "Evidence drill-down",
        "Every claim is traceable to evidence.",
        "get_evidence — live MCP response",
        TEAL,
    )


def scene_cta() -> str:
    parts = base("Get started")
    parts.extend(
        [
            text("Undocumented dependencies,", 600, 290, 50, weight=700, anchor="middle"),
            text("traced to evidence.", 600, 352, 50, fill=TEAL, weight=700, anchor="middle"),
            rect(320, 420, 560, 86, fill="#102B35", stroke=TEAL, radius=43, stroke_width=3),
            text(
                "RUN THE 5-MINUTE DEMO",
                600,
                472,
                24,
                fill=TEAL,
                weight=700,
                anchor="middle",
                spacing=1,
            ),
            badge("NO LLM KEY REQUIRED", 420, 530, 360, BLUE),
        ]
    )
    return finish(parts)


SCENES = [
    ("01-mismatch", 4, scene_mismatch),
    ("02-drift", 7, scene_drift),
    ("03-evidence", 7, scene_evidence),
    ("04-cta", 4, scene_cta),
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
            "400x225",
            "-tile",
            "2x2",
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
    print("Rendered evergreen README-demo scenes and storyboard.")


if __name__ == "__main__":
    main()
