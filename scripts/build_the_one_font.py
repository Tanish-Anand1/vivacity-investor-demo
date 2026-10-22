"""Convert the OFL Google Font to deterministic Three.js outline data.

Build-only dependencies: fonttools and skia-pathops (overlap removal).
No font service is needed by the film player.
"""
import json
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from fontTools.pens.basePen import BasePen
from fontTools.ttLib.removeOverlaps import removeOverlaps

ROOT = Path(__file__).resolve().parents[1]
folder = ROOT / "frontend/cinematic/fonts"
font = instantiateVariableFont(TTFont(folder / "InstrumentSans.ttf"), {"wght": 650, "wdth": 95})
removeOverlaps(font)
glyphs = font.getGlyphSet()
scale = 1000 / font["head"].unitsPerEm

class Outline(BasePen):
    def __init__(self):
        super().__init__(glyphs)
        self.commands = []
    def pt(self, p):
        return " ".join(str(round(v * scale, 3)) for v in p)
    def _moveTo(self, p):
        self.start = p
        self.commands.append("m " + self.pt(p))
    def _lineTo(self, p): self.commands.append("l " + self.pt(p))
    def _qCurveToOne(self, control, end): self.commands.append("q " + self.pt(end) + " " + self.pt(control))
    def _curveToOne(self, a, b, end): self.commands.append("b " + self.pt(end) + " " + self.pt(a) + " " + self.pt(b))
    def _closePath(self): self.commands.append("l " + self.pt(self.start))

out = {}
for char in "ABCDEFGHIJKLMNOPQRSTUVWXYZ ?":
    name = font.getBestCmap()[ord(char)]
    pen = Outline()
    glyphs[name].draw(pen)
    out[char] = {"ha": round(glyphs[name].width * scale, 3), "o": " ".join(pen.commands)}
data = {"glyphs": out, "familyName": "Instrument Sans", "resolution": 1000,
        "boundingBox": {"yMin": -250, "yMax": 1000}, "underlineThickness": 50,
        "original_font_information": {"license": "SIL OFL 1.1; see OFL.txt", "source": "Google Fonts / Instrument Sans"}}
(folder / "instrument-sans-outline.json").write_text(json.dumps(data, separators=(",", ":")), encoding="utf-8")
print("Wrote Instrument Sans 650 / width95 outlines")
