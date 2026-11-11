"""Overlay platform and Testnet4 marks on existing square SVG app icons."""

import argparse
from pathlib import Path
import subprocess
import tempfile
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
MARKS = ROOT / "assets/icon-overlays"
SVG = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG)
ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")


def mark(name):
    if name in {"apple", "tux"}:
        artwork = ET.parse(MARKS / f"{name}.svg").getroot()
        if "viewBox" not in artwork.attrib:
            artwork.set("viewBox", f"0 0 {artwork.get('width')} {artwork.get('height')}")
        if name == "apple":
            artwork.set("fill", "#ffffff")
        return artwork
    if name == "windows":
        paths = '<path fill="#3daeff" d="M2 2h21v21H2zm23 0h21v21H25zM2 25h21v21H2zm23 0h21v21H25z"/>'
    elif name == "testnet4":
        paths = (
            '<path fill="#0eab52" stroke="#0b4f2b" stroke-width="2" stroke-linejoin="round" '
            'd="M22 3h4l12 35H10L22 3Z"/>'
            '<path fill="#dbffd7" d="M18.7 13h10.6l2.5 7H16.2zm-5 14h20.6l2.5 7H11.2z"/>'
            '<path fill="#32dc70" stroke="#0b4f2b" stroke-width="2" stroke-linejoin="round" '
            'd="M10 37h28l8 6v3H2v-3z"/>'
        )
    else:
        raise ValueError(f"Unknown icon mark {name}")
    return ET.fromstring(f'<svg xmlns="{SVG}" viewBox="0 0 48 48">{paths}</svg>')


def compose_icon(source, target, *, platform=None, testnet4=False):
    text = source.read_text(encoding="utf-8")
    root = ET.fromstring(text)
    x, y, width, height = map(float, root.attrib["viewBox"].split())
    if root.tag != f"{{{SVG}}}svg" or width <= 0 or width != height or not text.rstrip().endswith("</svg>"):
        raise ValueError("Expected a square app SVG")

    overlays = []
    marks = {"macos": "apple", "windows": "windows", "linux": "tux"}
    if testnet4:
        overlays.append(("testnet4", 0, 0))
    if platform is not None:
        overlays.append((marks[platform], 0.68, 0.05))
    elements = []
    for name, left, top in overlays:
        artwork = mark(name)
        artwork.attrib.update({
            "x": f"{x + width * left:g}", "y": f"{y + height * top:g}",
            "width": f"{width * 0.28:g}", "height": f"{height * 0.28:g}",
            "opacity": "0.5", "data-mark": name, "aria-hidden": "true",
        })
        if name == "testnet4":
            # The previous cone's outer base ended at 94.4% of the square.
            baseline = 0.67 + 0.28 * 47 / 48
            artwork.attrib.update({
                "width": f"{width:g}", "height": f"{height * baseline:g}",
                "viewBox": "1 2 46 45", "preserveAspectRatio": "none",
            })
        elements.append(ET.tostring(artwork, encoding="unicode"))
    position = text.rfind("</svg>")
    target.write_text(text[:position] + "".join(elements) + text[position:], encoding="utf-8")


def render_platform_icons(catalog, output):
    with tempfile.TemporaryDirectory(prefix="app-icons-") as directory:
        variant = Path(directory) / "icon.svg"
        for app in ("qbit-core", "leap", "pins", "qord"):
            source = catalog / f"qbitleap-{app.removeprefix('qbit-')}-main/icon.svg"
            app_output = output / app
            app_output.mkdir(parents=True, exist_ok=True)
            for platform in ("macos", "windows", "linux", "umbrel"):
                for testnet4 in (False, True):
                    name = platform + ("-testnet4" if testnet4 else "")
                    compose_icon(source, variant, platform=None if platform == "umbrel" else platform,
                                 testnet4=testnet4)
                    subprocess.run(["rsvg-convert", "-w", "256", "-h", "256",
                                    "-o", app_output / f"{name}.png", variant], check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=ROOT)
    parser.add_argument("--output", type=Path, default=ROOT / "assets/platform-icons")
    args = parser.parse_args()
    render_platform_icons(args.catalog, args.output)
