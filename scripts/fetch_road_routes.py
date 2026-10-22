"""Fetch only missing directed pairs, at <=1 request/second; keep raw evidence."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import sys
import tempfile
import time
import urllib.request

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'skills/travel-workflow/scripts'))
import road_routes as roads

def save_validated_cache(points,a,b,cache,saved):
    # Same filesystem, so replace is atomic; invalid responses leave old evidence intact.
    with tempfile.TemporaryDirectory(prefix='candidate-',dir=cache) as candidate_dir:
        candidate=roads.cache_path(candidate_dir,roads.request_for(points,a,b))
        candidate.write_text(json.dumps(saved,ensure_ascii=False,indent=2),encoding='utf-8')
        leg=roads.read_leg(points,a,b,candidate_dir)
        candidate.replace(roads.cache_path(cache,roads.request_for(points,a,b)))
    return leg

def fetch_routes(places,anchors,trips,cache,refresh=False):
    points={**places,**anchors}
    cache=Path(cache)
    cache.mkdir(parents=True,exist_ok=True)
    pairs=[]
    for trip in trips:
        for _,a,b in roads.required_legs(trip):
            if (a,b) not in pairs:
                pairs.append((a,b))
    last=0
    for a,b in pairs:
        request=roads.request_for(points,a,b)
        path=roads.cache_path(cache,request)
        if path.exists() and not refresh:
            roads.read_leg(points,a,b,cache)
            print(f'cache: {a} -> {b}',flush=True)
            continue
        time.sleep(max(0,1.1-(time.monotonic()-last)))
        url=roads.request_url(request)
        last=time.monotonic()
        req=urllib.request.Request(url,headers={'User-Agent':'KKTravelLocalValidation/0.2 (personal local travel prototype)'})
        with urllib.request.urlopen(req,timeout=45) as response:
            payload=json.load(response)
        saved={'request':request,'request_url':url,'response':payload,'response_sha256':roads.hash_json(payload),'fetched_at':datetime.now(timezone.utc).isoformat()}
        leg=save_validated_cache(points,a,b,cache,saved)
        print(f'fetched: {a} -> {b}: {leg["distance_m"]:.0f} m, {leg["duration_s"]:.0f} s, snap {leg["snap_m"]}',flush=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--places',type=Path,required=True)
    parser.add_argument('--anchors',type=Path,required=True)
    parser.add_argument('--trip',type=Path,action='append',required=True)
    parser.add_argument('--cache',type=Path,required=True)
    parser.add_argument('--refresh',action='store_true')
    args=parser.parse_args()
    places={p.parent.name:json.loads(p.read_text(encoding='utf-8')) for p in args.places.glob('*/place.json')}
    trips=[json.loads(p.read_text(encoding='utf-8')) for p in args.trip]
    fetch_routes(places,roads.load_anchors(args.anchors),trips,args.cache,args.refresh)

if __name__=='__main__':
    main()
