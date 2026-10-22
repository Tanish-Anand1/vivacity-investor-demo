r"""Build review sheets from delivered films and the real browser handoff.

    python scripts/inspect_the_one.py
    python scripts/inspect_the_one.py --require-homepage \
        --homepage-landscape artifacts/the-one-browser-home-landscape.png \
        --homepage-portrait artifacts/the-one-browser-home-portrait.png

The first eight tiles are decoded from each MP4. The ninth must be a browser
screenshot captured after playback finishes. A missing browser capture remains
an explicitly pending tile; an encoded frame is never substituted for the app.
"""

from __future__ import annotations

import argparse
import json
import math
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
TIMES = (0.40, 1.40, 2.65, 3.65, 4.40, 5.10, 6.00, 6.90)
BEATS = (
    "FIRST CONTACT", "THE MACHINE", "THE INTERRUPTION", "WORLD FRACTURE",
    "ALTERNATE WORLDS", "CONVERGENCE", "VIVACITY", "ENTER ISABELLA LABS",
)
BACKGROUND = "#080a0c"
TEXT = "#eceae4"
SECONDARY = "#a9aaa8"


def font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for candidate in (Path("C:/Windows/Fonts/segoeui.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")):
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size)
    return ImageFont.load_default()


def probe(film: Path) -> dict:
    raw = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration,size:stream=width,height,nb_frames,codec_name,avg_frame_rate",
         "-of", "json", str(film)],
        text=True,
    )
    metadata = json.loads(raw)
    duration = float(metadata["format"]["duration"])
    if not math.isclose(duration, 7.5, abs_tol=0.001):
        raise ValueError(f"Expected a 7.500-second deliverable; {film.name} is {duration:.6f}s")
    return metadata


def locate_homepage(format_name: str, film: Path, explicit: Path | None) -> Path | None:
    if explicit is not None:
        supplied = explicit.resolve()
        if not supplied.is_file():
            raise FileNotFoundError(f"Browser homepage screenshot does not exist: {supplied}")
        return supplied
    candidates = [ROOT / f"artifacts/the-one-browser-home-{format_name}.png"]
    if format_name == "landscape":
        candidates.extend((ROOT / "frontend/test-results/the-one-opening").glob("**/homepage-after-opening.png"))
    else:
        candidates.extend((ROOT / "frontend/test-results/the-one-opening").glob("**/homepage-after-opening-portrait.png"))
    # A previous opening's screenshot cannot establish this film's handoff.
    current = [candidate for candidate in candidates if candidate.is_file() and candidate.stat().st_mtime >= film.stat().st_mtime]
    return max(current, key=lambda candidate: candidate.stat().st_mtime) if current else None


def paste_contained(sheet: Image.Image, source: Path, x: int, y: int, width: int, height: int) -> None:
    with Image.open(source) as opened:
        image = opened.convert("RGB")
        image.thumbnail((width, height), Image.Resampling.LANCZOS)
        sheet.paste(image, (x + (width - image.width) // 2, y + (height - image.height) // 2))


def review(format_name: str, homepage: Path | None) -> dict:
    film = ROOT / f"frontend/public/vivacity/the-one-isabella-{format_name}.mp4"
    if not film.is_file():
        raise FileNotFoundError(f"Encode the final film before inspection: {film}")
    metadata = probe(film)
    output = ROOT / f"artifacts/the-one-encoded-{format_name}"
    output.mkdir(parents=True, exist_ok=True)
    width, height = ((600, 338) if format_name == "landscape" else (270, 480))
    caption_height = 32
    sheet = Image.new("RGB", (width * 3, (height + caption_height) * 3), BACKGROUND)
    labels = ImageDraw.Draw(sheet)
    label_font = font(15 if format_name == "landscape" else 12)
    records = []
    for index, (time, beat) in enumerate(zip(TIMES, BEATS, strict=True)):
        frame = output / f"{time:.2f}s.png"
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(film),
             "-ss", f"{time:.2f}", "-frames:v", "1", str(frame)],
            check=True,
        )
        x, y = index % 3 * width, index // 3 * (height + caption_height)
        paste_contained(sheet, frame, x, y, width, height)
        labels.text((x + 10, y + height + 8), f"{time:04.2f} s  /  {beat}", fill=TEXT, font=label_font)
        records.append({"time_s": time, "beat": beat, "kind": "decoded_film_frame", "file": str(frame)})

    browser_capture = locate_homepage(format_name, film, homepage)
    x, y = width * 2, (height + caption_height) * 2
    if browser_capture:
        paste_contained(sheet, browser_capture, x, y, width, height)
        labels.text((x + 10, y + height + 8), "7.50 s  /  ACTIVE HOMEPAGE", fill=TEXT, font=label_font)
        records.append({
            "time_s": 7.5, "beat": "ACTIVE HOMEPAGE", "kind": "browser_screenshot", "file": str(browser_capture),
            "capture_semantics": "Browser screenshot after natural media completion; screenshot wall time can be later than 7.500s.",
        })
    else:
        pending = "Browser handoff capture pending.\n\nAn encoded frame cannot verify\nthe active homepage."
        labels.multiline_text((x + 20, y + height // 3), pending, fill=SECONDARY, font=font(16 if width > 300 else 12), spacing=8)
        labels.text((x + 10, y + height + 8), "7.50 s  /  PENDING BROWSER QA", fill=TEXT, font=label_font)
        records.append({"time_s": 7.5, "beat": "ACTIVE HOMEPAGE", "kind": "pending_browser_capture", "file": None})

    contact = output / "contact.png"
    sheet.save(contact)
    return {
        "format": format_name, "film": str(film), "contact": str(contact),
        "complete": browser_capture is not None, "frames": records, "video": metadata,
        "limits": "Contact sheets support visual inspection. They do not establish motion quality, accessibility, or interactivity on their own.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--format", choices=("both", "landscape", "portrait"), default="both")
    parser.add_argument("--homepage-landscape", type=Path)
    parser.add_argument("--homepage-portrait", type=Path)
    parser.add_argument("--require-homepage", action="store_true", help="Exit unsuccessfully if a real browser handoff capture is missing.")
    args = parser.parse_args()
    names = ("landscape", "portrait") if args.format == "both" else (args.format,)
    results = [review(name, getattr(args, f"homepage_{name}")) for name in names]
    report = {"schema_version": "vivacity.the-one-review/1.0", "complete": all(result["complete"] for result in results), "formats": results}
    report_path = ROOT / "artifacts/the-one-contact-sheets.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"complete": report["complete"], "report": str(report_path), "sheets": [result["contact"] for result in results]}, indent=2))
    return 1 if args.require_homepage and not report["complete"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
