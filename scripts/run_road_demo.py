"""Rebuild the three road-routing scenarios from local source and caches."""
import json
from pathlib import Path
import shutil
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/travel-workflow/scripts'))
from travel_sync import load_places,build,check
from road_routes import load_anchors

places=load_places(ROOT/'tests/fixtures/kota-kinabalu/places')
anchors=load_anchors(ROOT/'tests/fixtures/kota-kinabalu/anchors')
out=ROOT/'tests/output/road'
cache=ROOT/'tests/fixtures/kota-kinabalu/cache'
site=ROOT/'tests/output/site'
results=[]
for file in sorted((ROOT/'tests/fixtures/kota-kinabalu/scenarios/road').glob('*.json')):
    trip=json.loads(file.read_text(encoding='utf-8'))
    build(places,trip,out,anchors=anchors,route_cache=cache)
    result=check(places,trip,out,anchors=anchors,route_cache=cache)
    shutil.copytree(out,ROOT/'tests/output/evidence/road'/trip['revision'],dirs_exist_ok=True)
    shutil.copytree(out/'maps',site/trip['revision'],dirs_exist_ok=True)
    routing=json.loads((out/'routing.json').read_text(encoding='utf-8'))
    results.append({'revision':trip['revision'],'active':result['active_ids'],'source_digest':result['source_digest'],'files':len(result['files']),'legs':len(routing['legs']),'totals':routing['totals'],'hotel_departure':routing['hotel_departure'],'hotel_return':routing['hotel_return']})
shutil.copytree(out/'maps',site/'current',dirs_exist_ok=True)
(ROOT/'tests/output/evidence/road/results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
index='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>亚庇道路路线 · 本地验证</title><style>body{margin:0;background:#f6f5ef;font:15px system-ui,sans-serif;color:#203e48;display:flex;flex-direction:column;height:100vh}nav{display:flex;gap:18px;align-items:center;padding:13px 18px;flex-wrap:wrap;flex-shrink:0}a{color:#087e86}iframe{display:block;width:100%;flex:1;min-height:0;border:0}small{margin-left:auto}</style>
<nav><b>亚庇 · 道路路线验证</b><a href="01-baseline/route.html" target="map">原始三景点</a><a href="02-cancel/route.html" target="map">取消博物馆</a><a href="03-reorder/route.html" target="map">调整顺序</a><a href="current/route.html" target="map">当前版本</a><small>仅本地 · 模拟日游 / 未提供航班时刻</small></nav>
<iframe name="map" title="汽车道路地图" src="current/route.html"></iframe></html>'''
(site/'index.html').write_text(index,encoding='utf-8')
print(json.dumps(results,ensure_ascii=False,indent=2))
