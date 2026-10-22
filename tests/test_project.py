"""Exercise portable initialization and the real day-build entry point."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
FIXTURE=ROOT/'tests/fixtures/kota-kinabalu'


class ProjectTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((ROOT/'scripts/travel.py').exists(),'Reusable project entry point is missing')
        spec=importlib.util.spec_from_file_location('project_cli',ROOT/'scripts/travel.py')
        self.cli=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.cli)
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)/'new-project'
        self.cli.init_project(self.root)

    def test_new_project_is_empty_and_existing_target_is_not_overwritten(self):
        self.assertFalse(list((self.root/'travel').rglob('place.json')))
        self.assertFalse((self.root/'tests').exists())
        self.assertFalse((self.root/'.runtime').exists())
        self.assertEqual(list((self.root/'travel').rglob('anchor.json')),[])
        self.assertEqual(list((self.root/'travel/trips').iterdir()),[])
        note=self.root/'my-note.txt'
        note.write_text('keep',encoding='utf-8')
        with self.assertRaises(FileExistsError):
            self.cli.init_project(self.root)
        self.assertEqual(note.read_text(encoding='utf-8'),'keep')

    def test_new_trip_is_inspectable_draft_without_simulated_choices(self):
        self.cli.create_destination(self.root,'new-place','新目的地','Asia/Kuching')
        self.cli.create_trip(self.root,'first-trip','new-place','第一次旅行')
        status=self.cli.inspect_trip(self.root,'first-trip')
        self.assertEqual(status['planned_stops'],0)
        day=json.loads((self.root/'travel/trips/first-trip/days/day-01.json').read_text(encoding='utf-8'))
        self.assertFalse(day['simulation'])
        self.assertEqual(day['stops'],[])
        result=subprocess.run([sys.executable,'-X','utf8',str(self.root/'scripts/travel.py'),'inspect','--trip','first-trip'],cwd=self.tmp.name,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['planned_stops'],0)
        with self.assertRaisesRegex(ValueError,'草稿'):
            self.cli.build_day(self.root,'first-trip','day-01')
        self.assertFalse((self.root/'travel/trips/first-trip/generated/day-01').exists())
        with self.assertRaises(ValueError):
            self.cli.create_destination(self.root,'../outside','无效','Asia/Kuching')
        with self.assertRaises(FileExistsError):
            self.cli.create_trip(self.root,'first-trip','new-place','覆盖')

    def test_formal_build_uses_only_referenced_places_and_preserves_journal(self):
        self.cli.create_destination(self.root,'new-place','验证目的地','Asia/Kuching')
        self.cli.create_trip(self.root,'first-trip','new-place','验证旅程')
        destination=self.root/'travel/destinations/new-place'
        tripdir=self.root/'travel/trips/first-trip'
        shutil.copytree(FIXTURE/'places',destination/'places',dirs_exist_ok=True)
        shutil.copytree(FIXTURE/'anchors',destination/'anchors',dirs_exist_ok=True)
        shutil.copytree(FIXTURE/'cache',tripdir/'cache/routes',dirs_exist_ok=True)
        # An unfinished candidate must not prevent building already researched stops.
        candidate=destination/'places/unfinished'
        candidate.mkdir()
        (candidate/'place.json').write_text(json.dumps({'id':'unfinished','coordinates':[None,None]}),encoding='utf-8')
        trip=json.loads((tripdir/'trip.json').read_text(encoding='utf-8'))
        trip.update(transport_mode='driving',hotel_id='sheraton-kota-kinabalu',airport_id='bki-terminal-1')
        (tripdir/'trip.json').write_text(json.dumps(trip),encoding='utf-8')
        diary=tripdir/'journal/2026-10-22.md'
        diary.write_text('这是测试自己的记录，不是实际旅行。',encoding='utf-8')
        for scenario,expected in [('01-baseline',3),('02-cancel',2),('03-reorder',2)]:
            day=json.loads((FIXTURE/f'scenarios/road/{scenario}.json').read_text(encoding='utf-8'))
            day.update(status='ready',simulation=False)
            day.pop('travel')
            (tripdir/'days/day-01.json').write_text(json.dumps(day),encoding='utf-8')
            self.cli.build_day(self.root,'first-trip','day-01')
            self.cli.build_day(self.root,'first-trip','day-01',check_only=True)
            geo=json.loads((tripdir/'generated/day-01/maps/route.geojson').read_text(encoding='utf-8'))
            self.assertEqual(len([p for p in geo['features'] if p['geometry']['type']=='Point']),expected+2)
            self.assertEqual((tripdir/'site/day-01/route.html').read_bytes(),(tripdir/'generated/day-01/maps/route.html').read_bytes())
        self.assertEqual(diary.read_text(encoding='utf-8'),'这是测试自己的记录，不是实际旅行。')
        self.assertEqual(list((tripdir/'reviews').iterdir()),[])
        self.assertNotIn('unfinished',(tripdir/'generated/day-01/maps/route.geojson').read_text(encoding='utf-8'))
        self.assertTrue((tripdir/'generated/day-01/places/sabah-museum/README.md').exists())
        env=os.environ.copy()
        env['PYTHONPATH']=str(ROOT/'.runtime')
        result=subprocess.run([sys.executable,'-X','utf8',str(self.root/'scripts/travel.py'),'check','--trip','first-trip','--day','day-01'],cwd=self.tmp.name,env=env,capture_output=True,text=True,encoding='utf-8')
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(json.loads(result.stdout)['active'],['tanjung-aru','atkinson-clock-tower'])
        (tripdir/'site/day-01/route.html').write_text('stale preview',encoding='utf-8')
        with self.assertRaisesRegex(ValueError,'预览副本'):
            self.cli.build_day(self.root,'first-trip','day-01',check_only=True)
        # Changing the mode and removing a reference must not leave old views active.
        trip['transport_mode']='schematic'
        (tripdir/'trip.json').write_text(json.dumps(trip),encoding='utf-8')
        day['cancelled']=[]
        (tripdir/'days/day-01.json').write_text(json.dumps(day),encoding='utf-8')
        note=tripdir/'generated/day-01/personal-notes.md'
        note.write_text('preserve untracked note',encoding='utf-8')
        self.cli.build_day(self.root,'first-trip','day-01')
        self.cli.build_day(self.root,'first-trip','day-01',check_only=True)
        self.assertFalse((tripdir/'generated/day-01/routing.json').exists())
        self.assertFalse((tripdir/'generated/day-01/anchors.md').exists())
        self.assertFalse((tripdir/'generated/day-01/places/sabah-museum/README.md').exists())
        self.assertTrue((destination/'places/sabah-museum/place.json').exists())
        self.assertEqual(note.read_text(encoding='utf-8'),'preserve untracked note')
        self.assertEqual(diary.read_text(encoding='utf-8'),'这是测试自己的记录，不是实际旅行。')


if __name__=='__main__':
    unittest.main()
