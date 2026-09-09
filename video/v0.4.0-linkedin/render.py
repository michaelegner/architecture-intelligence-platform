from __future__ import annotations

import html
import subprocess
from pathlib import Path

WIDTH = 1080
HEIGHT = 1350
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


def badge(value: str, x: int, y: int, width: int, color: str) -> str:
    return "".join(
        [
            rect(x, y, width, 52, fill=f"{color}18", stroke=color, radius=26),
            text(value, x + width // 2, y + 35, 23, fill=color, weight=700, anchor="middle"),
        ]
    )


def logo(x: int, y: int, scale: float = 1) -> str:
    first = f"{x},{y + int(74 * scale)} {x + int(46 * scale)},{y} {x + int(76 * scale)},{y + int(42 * scale)}"
    second = f"{x + int(52 * scale)},{y + int(74 * scale)} {x + int(88 * scale)},{y + int(20 * scale)} {x + int(128 * scale)},{y + int(74 * scale)}"
    return (
        f'<polygon points="{first}" fill="url(#logoGradient)"/>'
        f'<polygon points="{second}" fill="url(#logoGradient2)"/>'
    )


def base(scene_number: int, section: str) -> list[str]:
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
        '<ellipse cx="920" cy="170" rx="330" ry="330" fill="url(#halo)"/>',
        logo(72, 62, 0.5),
        text("AIP", 150, 102, 32, weight=700),
        text("v0.4.0", 1000, 98, 24, fill=BLUE, weight=700, anchor="end", spacing=1),
        '<rect x="72" y="132" width="936" height="2" fill="#263653"/>',
        text(section.upper(), 72, 180, 20, fill=MUTED, weight=700, spacing=4),
        text(
            "github.com/michaelegner/architecture-intelligence-platform",
            540,
            1248,
            18,
            fill=MUTED,
            anchor="middle",
            family="DejaVu Sans Mono",
        ),
        f'<rect x="72" y="1280" width="{scene_number * 117}" height="4" rx="2" fill="{TEAL}"/>',
        f'<rect x="{72 + scene_number * 117}" y="1280" width="{936 - scene_number * 117}" height="4" rx="2" fill="#263653"/>',
        text(
            f"0{scene_number}", 1008, 1317, 18, fill=MUTED, anchor="end", family="DejaVu Sans Mono"
        ),
    ]


def finish(parts: list[str]) -> str:
    return "\n".join([*parts, "</svg>"])


def scene_release() -> str:
    parts = base(1, "Release")
    parts.extend(
        [
            logo(352, 305, 3),
            text("Architecture", 540, 665, 74, weight=700, anchor="middle"),
            text("Intelligence Platform", 540, 748, 74, weight=700, anchor="middle"),
            rect(215, 810, 650, 86, fill="#14213B", stroke=BLUE, radius=43),
            text(
                "RELEASE  v0.4.0", 540, 866, 30, fill=BLUE, weight=700, anchor="middle", spacing=2
            ),
            text("Trusted architecture context", 540, 1010, 43, weight=700, anchor="middle"),
            text("for AI agents.", 540, 1068, 43, fill=TEAL, weight=700, anchor="middle"),
        ]
    )
    return finish(parts)


def scene_problem() -> str:
    parts = base(2, "The problem")
    parts.extend(
        [
            text("AI agents need facts.", 72, 292, 62, weight=700),
            text("Not plausible guesses.", 72, 368, 62, fill=TEAL, weight=700),
            rect(72, 480, 420, 470, fill="#151A2A", stroke="#334155"),
            text("STALE CONTEXT", 282, 548, 18, fill=MUTED, weight=700, anchor="middle", spacing=2),
            text("architecture", 112, 650, 42, fill="#64748B", weight=700),
            text("diagram-v12-final", 112, 708, 32, fill="#64748B", family="DejaVu Sans Mono"),
            '<path d="M112 790 C190 720 250 850 334 760 S430 820 452 740" fill="none" stroke="#64748B" stroke-width="4" stroke-dasharray="12 12"/>',
            f'<line x1="112" y1="880" x2="452" y2="540" stroke="{RED}" stroke-width="8" stroke-linecap="round"/>',
            rect(550, 480, 458, 470, fill="#0F2530", stroke=TEAL),
            text(
                "TRUSTED CONTEXT", 779, 548, 18, fill=TEAL, weight=700, anchor="middle", spacing=2
            ),
            text("Declared + Observed", 779, 650, 32, weight=700, anchor="middle"),
            f'<circle cx="665" cy="775" r="34" fill="{BLUE}"/><circle cx="875" cy="775" r="34" fill="{AMBER}"/>',
            f'<line x1="700" y1="775" x2="840" y2="775" stroke="{TEAL}" stroke-width="6"/>',
            f'<circle cx="770" cy="775" r="48" fill="{PANEL_LIGHT}" stroke="{TEAL}" stroke-width="4"/>',
            text("✓", 770, 791, 46, fill=TEAL, weight=700, anchor="middle"),
            badge("EVIDENCE-BACKED", 628, 868, 302, TEAL),
            text(
                "Architecture claims an agent can verify.",
                540,
                1070,
                34,
                fill=MUTED,
                anchor="middle",
            ),
        ]
    )
    return finish(parts)


def scene_pipeline() -> str:
    parts = base(3, "Evidence pipeline")
    parts.extend(
        [
            text("Declared + observed", 72, 286, 62, weight=700),
            text("architecture.", 72, 360, 62, fill=TEAL, weight=700),
            rect(72, 470, 360, 156, fill="#101D38", stroke=BLUE),
            text("DECLARED", 112, 520, 20, fill=BLUE, weight=700, spacing=3),
            text("OpenAPI", 112, 576, 30, weight=700),
            text("AsyncAPI · architecture.yaml", 112, 612, 24, fill=MUTED),
            rect(648, 470, 360, 156, fill="#2B2110", stroke=AMBER),
            text("OBSERVED", 688, 520, 20, fill=AMBER, weight=700, spacing=3),
            text("OpenTelemetry", 688, 576, 30, weight=700),
            text("Runtime traces", 688, 612, 24, fill=MUTED),
            line(252, 636, 420, 778, stroke=BLUE, width=5),
            line(828, 636, 660, 778, stroke=AMBER, width=5),
            rect(300, 758, 480, 230, fill="#102B35", stroke=TEAL, radius=34, stroke_width=4),
            f'<circle cx="540" cy="828" r="46" fill="{TEAL}" opacity=".18"/>',
            text("◈", 540, 846, 58, fill=TEAL, weight=700, anchor="middle"),
            text(
                "EVIDENCE-BACKED", 540, 915, 24, fill=TEAL, weight=700, anchor="middle", spacing=1
            ),
            text("ARCHITECTURE GRAPH", 540, 957, 37, weight=700, anchor="middle"),
            text("Every fact keeps its evidence.", 540, 1090, 38, anchor="middle", weight=700),
        ]
    )
    return finish(parts)


def tool_card(name: str, purpose: str, y: int, color: str, index: str) -> str:
    return "".join(
        [
            rect(72, y, 936, 178, fill=PANEL, stroke=color),
            f'<circle cx="140" cy="{y + 89}" r="34" fill="{color}" opacity=".18"/>',
            text(
                index,
                140,
                y + 100,
                27,
                fill=color,
                weight=700,
                anchor="middle",
                family="DejaVu Sans Mono",
            ),
            text(name, 208, y + 78, 31, fill=TEXT, weight=700, family="DejaVu Sans Mono"),
            text(purpose, 208, y + 126, 25, fill=MUTED),
        ]
    )


def scene_tools() -> str:
    parts = base(4, "MCP surface")
    parts.extend(
        [
            text("Three read-only", 72, 286, 62, weight=700),
            text("MCP tools.", 72, 360, 62, fill=BLUE, weight=700),
            tool_card(
                "get_service_dependencies",
                "Explore direct, qualified dependencies",
                438,
                BLUE,
                "01",
            ),
            tool_card(
                "get_architecture_drift",
                "Find declared-versus-observed discrepancies",
                642,
                AMBER,
                "02",
            ),
            tool_card("get_evidence", "Resolve the provenance behind every claim", 846, TEAL, "03"),
            badge("READ-ONLY", 72, 1085, 240, BLUE),
            badge("DETERMINISTIC", 332, 1085, 278, TEAL),
            badge("NO LLM REQUIRED", 630, 1085, 378, PURPLE),
        ]
    )
    return finish(parts)


def scene_drift() -> str:
    parts = base(5, "Drift discovery")
    parts.extend(
        [
            text("Find what reality", 72, 286, 62, weight=700),
            text("never declared.", 72, 360, 62, fill=AMBER, weight=700),
            rect(72, 414, 936, 720, fill="#080D18", stroke="#334155", radius=26),
            rect(92, 440, 896, 600, fill="#050810", stroke=AMBER, radius=16),
            text("TELLA CAPTURE", 540, 694, 24, fill=AMBER, weight=700, anchor="middle", spacing=3),
            text(
                "05-drift-tella.mp4",
                540,
                746,
                28,
                fill=MUTED,
                anchor="middle",
                family="DejaVu Sans Mono",
            ),
            text(
                "Real tools/call request + OBSERVED_ONLY result",
                540,
                800,
                24,
                fill=MUTED,
                anchor="middle",
            ),
            badge("LIVE MCP RESPONSE", 212, 1060, 314, AMBER),
            badge("JSON-RPC / HTTP", 550, 1060, 318, BLUE),
        ]
    )
    return finish(parts)


def scene_evidence() -> str:
    parts = base(6, "Evidence drill-down")
    parts.extend(
        [
            text("From claim", 72, 286, 62, weight=700),
            text("to provenance.", 72, 360, 62, fill=TEAL, weight=700),
            rect(72, 414, 936, 720, fill="#080D18", stroke="#334155", radius=26),
            rect(92, 440, 896, 600, fill="#050810", stroke=TEAL, radius=16),
            text("TELLA CAPTURE", 540, 694, 24, fill=TEAL, weight=700, anchor="middle", spacing=3),
            text(
                "06-evidence-tella.mp4",
                540,
                746,
                28,
                fill=MUTED,
                anchor="middle",
                family="DejaVu Sans Mono",
            ),
            text(
                "Real evidence resolution at the same snapshot",
                540,
                800,
                24,
                fill=MUTED,
                anchor="middle",
            ),
            badge("SAME SNAPSHOT", 132, 1060, 320, BLUE),
            badge("SANITIZED PROVENANCE", 476, 1060, 472, TEAL),
        ]
    )
    return finish(parts)


def value_card(title: str, subtitle: str, x: int, y: int, color: str, symbol: str) -> str:
    return "".join(
        [
            rect(x, y, 448, 250, fill=PANEL, stroke=color),
            f'<circle cx="{x + 62}" cy="{y + 64}" r="32" fill="{color}" opacity=".18"/>',
            text(symbol, x + 62, y + 75, 30, fill=color, weight=700, anchor="middle"),
            text(title, x + 34, y + 145, 31, weight=700),
            text(subtitle, x + 34, y + 190, 22, fill=MUTED),
        ]
    )


def scene_value() -> str:
    parts = base(7, "Release value")
    parts.extend(
        [
            text("Context an agent", 72, 286, 62, weight=700),
            text("can trust.", 72, 360, 62, fill=TEAL, weight=700),
            value_card("Qualified claims", "Fact, discrepancy, or unknown", 72, 452, GREEN, "✓"),
            value_card("Stable snapshots", "One consistent graph state", 560, 452, BLUE, "◷"),
            value_card(
                "Traceable provenance", "Evidence behind every answer", 72, 742, PURPLE, "◎"
            ),
            value_card("Zero graph writes", "Agents can read, never rewrite", 560, 742, AMBER, "◇"),
            text(
                "Deterministic architecture intelligence through MCP.",
                540,
                1115,
                31,
                fill=MUTED,
                anchor="middle",
            ),
        ]
    )
    return finish(parts)


def scene_cta() -> str:
    parts = base(8, "Open source")
    parts.extend(
        [
            text("23 scenarios.", 540, 420, 70, weight=700, anchor="middle"),
            text("Two clean runs.", 540, 515, 70, weight=700, anchor="middle"),
            text("Byte-identical", 540, 610, 70, fill=TEAL, weight=700, anchor="middle"),
            text("semantic output.", 540, 695, 70, fill=TEAL, weight=700, anchor="middle"),
            rect(132, 800, 816, 118, fill="#102B35", stroke=TEAL, radius=59, stroke_width=3),
            text(
                "EXPLORE v0.4.0 ON GITHUB",
                540,
                873,
                25,
                fill=TEAL,
                weight=700,
                anchor="middle",
                spacing=1,
            ),
            text(
                "github.com/michaelegner/",
                540,
                1005,
                28,
                fill=MUTED,
                anchor="middle",
                family="DejaVu Sans Mono",
            ),
            text(
                "architecture-intelligence-platform",
                540,
                1045,
                28,
                fill=TEXT,
                weight=700,
                anchor="middle",
                family="DejaVu Sans Mono",
            ),
            badge("MCP 2026-07-28", 382, 1120, 316, BLUE),
        ]
    )
    return finish(parts)


SCENES = [
    ("01-release", 4, scene_release),
    ("02-problem", 5, scene_problem),
    ("03-pipeline", 10, scene_pipeline),
    ("04-tools", 7, scene_tools),
    ("05-drift", 12, scene_drift),
    ("06-evidence", 11, scene_evidence),
    ("07-value", 6, scene_value),
    ("08-cta", 5, scene_cta),
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
            "270x338",
            "-tile",
            "4x2",
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
    print("Rendered Canva-ready scenes and storyboard.")


if __name__ == "__main__":
    main()
