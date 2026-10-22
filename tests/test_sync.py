import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("travel_sync", ROOT / "skills/travel-workflow/scripts/travel_sync.py")
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.out = Path(self.tmp.name) / "current"
        self.places = sync.load_places(ROOT / "tests/fixtures/kota-kinabalu/places")
        self.cases = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((ROOT / "tests/fixtures/kota-kinabalu/scenarios/schematic").glob("*.json"))]

    def tearDown(self):
        self.tmp.cleanup()

    def build(self, n):
        sync.build(self.places, self.cases[n], self.out)
        sync.check(self.places, self.cases[n], self.out)
        return json.loads((self.out / "maps/route.geojson").read_text(encoding="utf-8"))

    def test_cancel_then_reorder_updates_all_views(self):
        original = copy.deepcopy(self.places)
        a = self.build(0)
        self.assertEqual([f["properties"]["place_id"] for f in a["features"] if f["geometry"]["type"] == "Point"], ["atkinson-clock-tower", "sabah-museum", "tanjung-aru"])
        b = self.build(1)
        self.assertEqual(len(b["features"]), 3)  # 2 points + 1 link
        self.assertNotIn("sabah-museum", json.dumps(b))
        self.assertNotIn("sabah-museum", (self.out / "maps/route.html").read_text(encoding="utf-8"))
        guide = (self.out / "places/sabah-museum/README.md").read_text(encoding="utf-8")
        self.assertIn("本次已取消", guide)
        self.assertIn("RM15", guide)
        self.assertIn("https://museum.sabah.gov.my/node/68", guide)
        c = self.build(2)
        points = [f for f in c["features"] if f["geometry"]["type"] == "Point"]
        self.assertEqual([f["properties"]["place_id"] for f in points], ["tanjung-aru", "atkinson-clock-tower"])
        self.assertEqual([f["properties"]["start"] for f in points], ["09:00", "14:00"])
        line = c["features"][-1]
        self.assertEqual(line["geometry"]["coordinates"], [[116.048889, 5.942778], [116.077306, 5.982194]])
        text = (self.out / "places/tanjung-aru/README.md").read_text(encoding="utf-8")
        self.assertIn("本次不安排日落拍照", text)
        self.assertNotIn("16:30", text)
        itinerary = (self.out / "itinerary.md").read_text(encoding="utf-8")
        self.assertIn("已知门票小计：RM0", itinerary)
        self.assertIn("不是旅行总费用", itinerary)
        self.assertEqual(self.places, original)
        self.assertFalse((self.out / "reviews").exists())

    def test_rebuild_is_idempotent_and_preserves_notes(self):
        self.build(2)
        (self.out / "personal-notes.md").write_text("用户自己的笔记", encoding="utf-8")
        before = {str(p.relative_to(self.out)): p.read_bytes() for p in self.out.rglob("*") if p.is_file()}
        self.build(2)
        after = {str(p.relative_to(self.out)): p.read_bytes() for p in self.out.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_old_source_and_tampered_map_are_detected(self):
        self.build(0)
        with self.assertRaisesRegex(ValueError, "过期|不同步"):
            sync.check(self.places, self.cases[2], self.out)
        self.build(2)
        p = self.out / "maps/route.geojson"
        d = json.loads(p.read_text(encoding="utf-8"))
        d["features"][0]["properties"]["start"] = "16:30"
        p.write_text(json.dumps(d), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "损坏|不同步"):
            sync.check(self.places, self.cases[2], self.out)

    def test_invalid_stop_does_not_overwrite_good_build(self):
        self.build(0)
        before = (self.out / "manifest.json").read_bytes()
        broken = copy.deepcopy(self.cases[2])
        broken["stops"][0]["place_id"] = "does-not-exist"
        with self.assertRaises(ValueError):
            sync.build(self.places, broken, self.out)
        self.assertEqual(before, (self.out / "manifest.json").read_bytes())

    def test_missing_guide_cannot_be_hidden_by_manifest(self):
        self.build(2)
        manifest_path = self.out / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        del manifest["files"]["places/sabah-museum/README.md"]
        manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "清单"):
            sync.check(self.places, self.cases[2], self.out)

    def test_duplicated_ids_and_inconsistent_time_rejected(self):
        broken = copy.deepcopy(self.cases[0])
        broken["stops"][1]["place_id"] = "atkinson-clock-tower"
        with self.assertRaises(ValueError):
            sync.build(self.places, broken, self.out)
        broken = copy.deepcopy(self.cases[0])
        broken["stops"][0]["start"] = "18:00"
        with self.assertRaises(ValueError):
            sync.build(self.places, broken, self.out)


if __name__ == "__main__":
    unittest.main()
