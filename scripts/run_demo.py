"""Reproduce the three authorized local simulations; keep source and personal notes."""
import json
from pathlib import Path
import shutil
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skills/travel-workflow/scripts"))
from travel_sync import build, check, load_places

ROOT = Path(__file__).resolve().parents[1]
places = load_places(ROOT / "tests/fixtures/kota-kinabalu/places")
out = ROOT / "tests/output/schematic"
results = []
for source in sorted((ROOT / "tests/fixtures/kota-kinabalu/scenarios/schematic").glob("*.json")):
    trip = json.loads(source.read_text(encoding="utf-8"))
    build(places, trip, out)
    report = check(places, trip, out)
    shutil.copytree(out, ROOT / "tests/output/evidence/schematic" / trip["revision"], dirs_exist_ok=True)
    results.append({"revision": trip["revision"], "order": report["active_ids"], "known_ticket_myr": report["known_ticket_myr"], "checked_files": len(report["files"]), "source_digest": report["source_digest"]})
(ROOT / "tests/output/evidence/schematic/results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(results, ensure_ascii=False, indent=2))
