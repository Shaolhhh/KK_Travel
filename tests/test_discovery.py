"""Discovery must work before scheduling, stay fresh, and preserve user records."""
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class DiscoveryTests(unittest.TestCase):
    def setUp(self):
        spec=importlib.util.spec_from_file_location('travel_cli_discovery',ROOT/'scripts/travel.py')
        self.cli=importlib.util.module_from_spec(spec); spec.loader.exec_module(self.cli)
        self.tmp=tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'project'; self.cli.init_project(self.root)
        self.cli.create_destination(self.root,'test-city','测试城','Asia/Kuching')
        self.cli.create_trip(self.root,'test-trip','test-city','测试旅行')
        self.dest=self.root/'travel/destinations/test-city'
        self.trip=self.root/'travel/trips/test-trip'
        shutil.copytree(ROOT/'tests/fixtures/kota-kinabalu/places',self.dest/'places',dirs_exist_ok=True)
        self.cli.write(self.trip/'selection.json',{'items':[{'place_id':'tanjung-aru','status':'candidate','reason':'待筛选'}]})

    def build(self,check=False):
        self.assertTrue(hasattr(self.cli,'build_web'),'Missing unscheduled discovery web entry point')
        return self.cli.build_web(self.root,'test-trip',check_only=check)

    def test_draft_can_generate_web_without_creating_a_schedule(self):
        before=(self.trip/'days/day-01.json').read_bytes()
        result=self.build()
        self.assertEqual(result['candidates'],1)
        self.assertEqual((self.trip/'days/day-01.json').read_bytes(),before)
        self.assertTrue((self.root/'docs/site/test-trip/index.html').is_file())
        geo=self.cli.read(self.root/'docs/site/test-trip/recognition.geojson')
        self.assertTrue(all(f['geometry']['type']=='Point' for f in geo['features']))
        self.assertEqual([f['properties']['id'] for f in geo['features']],['tanjung-aru'])
        self.build(True)

    def test_selection_and_coordinate_changes_invalidate_old_web(self):
        self.build()
        p=self.dest/'places/tanjung-aru/place.json'; place=self.cli.read(p)
        place['coordinates']=[116.1,6.0]; self.cli.write(p,place)
        with self.assertRaisesRegex(ValueError,'过期|不同步'):
            self.build(True)
        self.cli.write(self.trip/'selection.json',{'items':[{'place_id':'tanjung-aru','status':'excluded','reason':'本次跳过'}]})
        self.build(); self.build(True)
        geo=self.cli.read(self.root/'docs/site/test-trip/recognition.geojson')
        self.assertEqual(geo['features'][0]['geometry']['coordinates'],[116.1,6.0])
        self.assertEqual(geo['features'][0]['properties']['status'],'excluded')
        self.assertEqual(geo['features'][0]['properties']['reason'],'本次跳过')
        self.assertEqual(self.cli.inspect_trip(self.root,'test-trip')['planned_stops'],0)

    def test_web_build_is_deterministic_and_does_not_publish_journal_or_private_files(self):
        (self.trip/'journal/note.md').write_text('PRIVATE TEST DIARY','utf8')
        (self.trip/'private').mkdir(); (self.trip/'private/booking.txt').write_text('PRIVATE BOOKING','utf8')
        self.build(); site=self.root/'docs/site/test-trip'
        before={p.name:p.read_bytes() for p in site.iterdir() if p.is_file()}
        self.build()
        self.assertEqual(before,{p.name:p.read_bytes() for p in site.iterdir() if p.is_file()})
        self.assertNotIn('PRIVATE TEST DIARY',(site/'index.html').read_text('utf8'))
        self.assertFalse((site/'private').exists())
        (site/'index.html').write_text('stale','utf8')
        with self.assertRaisesRegex(ValueError,'过期|不同步'):
            self.build(True)

if __name__=='__main__': unittest.main()
