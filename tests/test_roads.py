import copy
import importlib.util
import json
from pathlib import Path
import sys
import shutil
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills/travel-workflow/scripts'))
import travel_sync as sync


class RoadTests(unittest.TestCase):
    def setUp(self):
        self.places = sync.load_places(ROOT / 'tests/fixtures/kota-kinabalu/places')
        self.anchors = {p.parent.name: json.loads(p.read_text(encoding='utf-8')) for p in (ROOT/'tests/fixtures/kota-kinabalu/anchors').glob('*/anchor.json')}
        self.trip = json.loads((ROOT/'tests/fixtures/kota-kinabalu/scenarios/schematic/01-baseline.json').read_text(encoding='utf-8'))
        self.trip['travel'] = {'hotel_id':'sheraton-kota-kinabalu', 'airport_id':'bki-terminal-1', 'profile':'driving', 'buffer_minutes':15}

    def test_driving_request_must_not_silently_use_straight_lines(self):
        with tempfile.TemporaryDirectory() as out:
            with self.assertRaisesRegex(ValueError, '道路.*缓存|道路.*数据'):
                sync.build(self.places, self.trip, Path(out))

    def test_real_cached_routes_include_round_trip_and_direction(self):
        import road_routes as roads
        legs = roads.required_legs(self.trip)
        self.assertEqual(legs, [
            ('arrival','bki-terminal-1','sheraton-kota-kinabalu'),
            ('day','sheraton-kota-kinabalu','atkinson-clock-tower'),
            ('day','atkinson-clock-tower','sabah-museum'),
            ('day','sabah-museum','tanjung-aru'),
            ('day','tanjung-aru','sheraton-kota-kinabalu'),
            ('departure','sheraton-kota-kinabalu','bki-terminal-1')])
        model = roads.assemble(self.places, self.anchors, self.trip, ROOT/'tests/fixtures/kota-kinabalu/cache')
        self.assertEqual(len(model['legs']),6)
        self.assertTrue(all(len(x['geometry']['coordinates'])>2 for x in model['legs']))
        self.assertTrue(all(x['distance_m']>0 and x['duration_s']>0 for x in model['legs']))
        self.assertEqual(model['totals']['day']['distance_m'], sum(x['distance_m'] for x in model['legs'] if x['group']=='day'))
        self.assertNotEqual(model['legs'][0]['geometry']['coordinates'], list(reversed(model['legs'][-1]['geometry']['coordinates'])))

    def test_map_caption_and_airport_reference_are_not_fixed_to_demo(self):
        import road_routes as roads
        import road_maps
        self.anchors['sheraton-kota-kinabalu']['name']='测试酒店'
        self.anchors['bki-terminal-1']['name']='测试机场第二航站楼'
        self.anchors['bki-terminal-1']['coordinate_precision']='第二航站楼测试代表点'
        model=roads.assemble(self.places,self.anchors,self.trip,ROOT/'tests/fixtures/kota-kinabalu/cache')
        data=roads.geojson(self.places,self.anchors,self.trip,model,'test')
        drawn=[]
        original_draw=road_maps.ImageDraw.Draw
        class RecordingDraw:
            def __init__(self,*args,**kwargs): self.delegate=original_draw(*args,**kwargs)
            def __getattr__(self,name): return getattr(self.delegate,name)
            def text(self,xy,text,*args,**kwargs):
                drawn.append(text)
                return self.delegate.text(xy,text,*args,**kwargs)
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(road_maps.ImageDraw,'Draw',RecordingDraw):
                road_maps.static(data,'其他酒店测试',Path(tmp)/'map.png')
        self.assertNotIn('亚庇喜来登酒店',' '.join(drawn))
        self.assertNotIn('BKI T1',' '.join(drawn))
        self.assertEqual(model['airport_reference'],'第二航站楼测试代表点')

    def test_cancel_and_reorder_replace_leg_geometry_keep_anchors(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            original=copy.deepcopy(self.places)
            for filename in ['01-baseline','02-cancel','03-reorder']:
                trip=json.loads((ROOT/f'tests/fixtures/kota-kinabalu/scenarios/schematic/{filename}.json').read_text(encoding='utf-8'))
                trip['travel']=self.trip['travel']
                sync.build(self.places,trip,out,anchors=self.anchors,route_cache=ROOT/'tests/fixtures/kota-kinabalu/cache')
                sync.check(self.places,trip,out,anchors=self.anchors,route_cache=ROOT/'tests/fixtures/kota-kinabalu/cache')
                data=json.loads((out/'maps/route.geojson').read_text(encoding='utf-8'))
                points=[x for x in data['features'] if x['geometry']['type']=='Point']
                lines=[x for x in data['features'] if x['properties'].get('kind')=='road']
                self.assertEqual(len(points),5 if filename=='01-baseline' else 4)
                self.assertEqual(len(lines),6 if filename=='01-baseline' else 5)
                self.assertTrue({'sheraton-kota-kinabalu','bki-terminal-1'} <= {p['properties']['place_id'] for p in points})
                self.assertTrue(all(x['properties']['kind']!='schematic' for x in lines))
                if filename!='01-baseline':
                    self.assertNotIn('sabah-museum',json.dumps(data))
                    self.assertIn('本次已取消',(out/'places/sabah-museum/README.md').read_text(encoding='utf-8'))
                    self.assertIn('RM15',(out/'places/sabah-museum/README.md').read_text(encoding='utf-8'))
                if filename=='03-reorder':
                    day=[x for x in lines if x['properties']['group']=='day']
                    self.assertEqual([(x['properties']['from'],x['properties']['to']) for x in day],[('sheraton-kota-kinabalu','tanjung-aru'),('tanjung-aru','atkinson-clock-tower'),('atkinson-clock-tower','sheraton-kota-kinabalu')])
                    self.assertIn('本次不安排日落拍照',(out/'places/tanjung-aru/README.md').read_text(encoding='utf-8'))
            self.assertEqual(original,self.places)
            before={p.relative_to(out):p.read_bytes() for p in out.rglob('*') if p.is_file()}
            sync.build(self.places,trip,out,anchors=self.anchors,route_cache=ROOT/'tests/fixtures/kota-kinabalu/cache')
            self.assertEqual(before,{p.relative_to(out):p.read_bytes() for p in out.rglob('*') if p.is_file()})

    def test_coordinates_change_cannot_reuse_old_route(self):
        import road_routes as roads
        self.anchors['sheraton-kota-kinabalu']['coordinates'][0]+=0.001
        with self.assertRaisesRegex(ValueError,'缓存'):
            roads.assemble(self.places,self.anchors,self.trip,ROOT/'tests/fixtures/kota-kinabalu/cache')

    def test_too_short_transfer_gap_is_rejected(self):
        import road_routes as roads
        self.trip['stops'][1]['start']='09:46'
        with self.assertRaisesRegex(ValueError,'交通时间不足'):
            roads.assemble(self.places,self.anchors,self.trip,ROOT/'tests/fixtures/kota-kinabalu/cache')

    def test_missing_routes_leave_previous_output_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'output'
            sync.build(self.places,self.trip,out,anchors=self.anchors,route_cache=ROOT/'tests/fixtures/kota-kinabalu/cache')
            before=(out/'manifest.json').read_bytes()
            with self.assertRaisesRegex(ValueError,'缓存'):
                sync.build(self.places,self.trip,out,anchors=self.anchors,route_cache=Path(tmp)/'empty')
            self.assertEqual(before,(out/'manifest.json').read_bytes())

    def test_route_cache_refresh_invalidates_old_output(self):
        import road_routes as roads
        with tempfile.TemporaryDirectory() as tmp:
            out,cache=Path(tmp)/'output',Path(tmp)/'cache'
            shutil.copytree(ROOT/'tests/fixtures/kota-kinabalu/cache',cache)
            sync.build(self.places,self.trip,out,anchors=self.anchors,route_cache=cache)
            request=roads.request_for({**self.places,**self.anchors},'bki-terminal-1','sheraton-kota-kinabalu')
            path=roads.cache_path(cache,request)
            entry=json.loads(path.read_text(encoding='utf-8'))
            entry['response']['routes'][0]['duration']+=60
            entry['response']['routes'][0]['legs'][0]['duration']+=60
            entry['response_sha256']=roads.hash_json(entry['response'])
            path.write_text(json.dumps(entry),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'过期'):
                sync.check(self.places,self.trip,out,anchors=self.anchors,route_cache=cache)

    def test_road_html_tamper_is_detected_even_when_embedded_json_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)
            sync.build(self.places,self.trip,out,anchors=self.anchors,route_cache=ROOT/'tests/fixtures/kota-kinabalu/cache')
            path=out/'maps/route.html'
            page=path.read_text(encoding='utf-8')
            path.write_text(page.replace('11:00–13:00','10:00–13:00',1),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'损坏|不同步'):
                sync.check(self.places,self.trip,out,anchors=self.anchors,route_cache=ROOT/'tests/fixtures/kota-kinabalu/cache')

    def test_invalid_refresh_preserves_previous_cache_and_valid_refresh_replaces_it(self):
        import road_routes as roads
        spec=importlib.util.spec_from_file_location('fetch_road_routes',ROOT/'scripts/fetch_road_routes.py')
        fetch=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(fetch)
        points={**self.places,**self.anchors}
        a,b='bki-terminal-1','sheraton-kota-kinabalu'
        request=roads.request_for(points,a,b)
        with tempfile.TemporaryDirectory() as tmp:
            cache=Path(tmp)
            target=roads.cache_path(cache,request)
            shutil.copyfile(roads.cache_path(ROOT/'tests/fixtures/kota-kinabalu/cache',request),target)
            before=target.read_bytes()
            original=json.loads(before)
            for bad in ['NoRoute','snap']:
                entry=copy.deepcopy(original)
                if bad=='NoRoute':
                    entry['response']={'code':'NoRoute','message':'No route found'}
                else:
                    entry['response']['waypoints'][0]['distance']=999
                entry['response_sha256']=roads.hash_json(entry['response'])
                with self.assertRaises(ValueError):
                    fetch.save_validated_cache(points,a,b,cache,entry)
                self.assertEqual(target.read_bytes(),before)
                self.assertEqual(len(list(cache.iterdir())),1)
            original['fetched_at']='2026-10-22T00:00:00+00:00'
            fetch.save_validated_cache(points,a,b,cache,original)
            self.assertNotEqual(target.read_bytes(),before)
            self.assertEqual(roads.read_leg(points,a,b,cache)['fetched_at'],original['fetched_at'])


if __name__=='__main__':
    unittest.main()
