"""Capture the nine approved review timestamps from the encoded opening films.

Run after encode_isabella_cinematic.ps1. The contact sheets represent bytes
actually shipped to browsers, not the uncompressed Three.js render source.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw


ROOT = Path(__file__).resolve().parents[1]
# The encoded film's last frame is at 7.483 s; at 7.500 s the real homepage
# replaces it, which is inspected separately in the browser test.
TIMES = (0.30, 0.90, 1.80, 2.60, 3.50, 4.60, 5.60, 6.50, 7.45)


def review(format_name: str) -> dict:
    film = ROOT / f"frontend/public/vivacity/isabella-impossible-{format_name}.mp4"
    output = ROOT / f"artifacts/isabella-cinema-encoded-{format_name}"
    output.mkdir(parents=True, exist_ok=True)
    width, height = ((480, 270) if format_name == "landscape" else (216, 384))
    sheet = Image.new("RGB", (width * 3, height * 3), "#030504")
    labels = ImageDraw.Draw(sheet)
    for index, time in enumerate(TIMES):
        frame = output / f"{time:.2f}s.png"
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(film),
             "-ss", str(time), "-frames:v", "1", str(frame)],
            check=True,
        )
        with Image.open(frame) as source:
            image = source.convert("RGB")
            image.thumbnail((width, height), Image.Resampling.LANCZOS)
        x, y = index % 3 * width, index // 3 * height
        sheet.paste(image, (x + (width - image.width) // 2, y + (height - image.height) // 2))
        labels.rectangle((x, y, x + 73, y + 20), fill="#030504")
        labels.text((x + 7, y + 4), f"{time:.2f} s", fill="white")
    contact = output / "contact.png"
    sheet.save(contact)
    metadata = subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=width,height,nb_frames,codec_name", "-of", "json", str(film)],
        text=True,
    )
    return {"format": format_name, "film": str(film), "contact": str(contact),
            "video": json.loads(metadata)}


if __name__ == "__main__":
    print(json.dumps([review(name) for name in ("landscape", "portrait")], indent=2))
