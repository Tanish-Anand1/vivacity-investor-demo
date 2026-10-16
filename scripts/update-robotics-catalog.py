"""Export the authoritative scenario catalog for the frontend's idle picker."""
from pathlib import Path
import json
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from vivacity.templates import catalog

path = Path(__file__).resolve().parents[1] / 'frontend/src/generated/templates.json'
path.write_text(json.dumps(catalog(), indent=2) + '\n', encoding='utf-8')
