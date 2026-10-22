"""Local travel project lifecycle; no default test data or network calls."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import shutil
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
ASSETS=ROOT/'skills/travel-workflow/assets'
sys.path.insert(0,str(ROOT/'skills/travel-workflow/scripts'))


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))


def write(path,value):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    Path(path).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def stable_id(value):
    reserved={'con','prn','aux','nul'}|{f'{prefix}{i}' for prefix in ('com','lpt') for i in range(1,10)}
    if not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*',value) or value in reserved:
        raise ValueError('ID须用小写英文、数字和连字符，不能是路径或系统保留名称')
    return value


def inside(root,*parts):
    root=Path(root).resolve()
    path=root.joinpath(*parts).resolve()
    if not path.is_relative_to(root):
        raise ValueError('路径必须留在当前项目内')
    return path


def init_project(target):
    target=Path(target).resolve()
    if target.exists():
        raise FileExistsError('目标已存在；新项目不会覆盖原目录')
    target.mkdir(parents=True)
    for directory in ('travel/destinations','travel/trips','scripts','docs'):
        (target/directory).mkdir(parents=True,exist_ok=True)
    for name in ('travel.py','fetch_road_routes.py','serve_maps.py'):
        shutil.copy2(ROOT/'scripts'/name,target/'scripts'/name)
    shutil.copytree(ROOT/'skills/travel-workflow',target/'skills/travel-workflow',ignore=shutil.ignore_patterns('__pycache__','*.pyc'))
    for name in ('workflow.md','data-model.md'):
        shutil.copy2(ROOT/'docs'/name,target/'docs'/name)
    for name in ('AGENTS.md','requirements.txt','.gitignore'):
        shutil.copy2(ROOT/name,target/name)
    shutil.copy2(ASSETS/'project-readme.md',target/'README.md')
    write(target/'project.json',{'schema_version':1,'template_version':'1.1','data_root':'travel'})
    return target


def create_destination(root,key,name,timezone):
    stable_id(key)
    if not name.strip() or not timezone.strip():
        raise ValueError('目的地名称与时区不可为空')
    folder=inside(root,'travel/destinations',key)
    if folder.exists():
        raise FileExistsError('目的地已存在，请维护已有资料')
    for part in ('places','anchors','maps'):
        (folder/part).mkdir(parents=True,exist_ok=True)
    write(folder/'destination.json',{'schema_version':1,'id':key,'name':name,'timezone':timezone})
    shutil.copy2(ASSETS/'destination.md',folder/'overview.md')
    return folder


def create_trip(root,key,destination,title):
    stable_id(key)
    stable_id(destination)
    place=read(inside(root,'travel/destinations',destination,'destination.json'))
    folder=inside(root,'travel/trips',key)
    if folder.exists():
        raise FileExistsError('旅程已存在，请维护已有计划')
    for part in ('days','journal','reviews','cache/routes','generated','site'):
        (folder/part).mkdir(parents=True,exist_ok=True)
    trip=read(ASSETS/'trip.json')
    trip.update(id=key,destination_id=destination,title=title)
    write(folder/'trip.json',trip)
    day=read(ASSETS/'day.json')
    day.update(id=f'{key}-day-01',timezone=place['timezone'])
    write(folder/'days/day-01.json',day)
    write(folder/'selection.json',{'items':[]})
    shutil.copy2(ASSETS/'traveler.md',folder/'requirements.md')
    shutil.copy2(ASSETS/'decisions.md',folder/'decisions.md')
    return folder


def trip_context(root,key):
    stable_id(key)
    folder=inside(root,'travel/trips',key)
    trip=read(folder/'trip.json')
    if trip['id']!=key:
        raise ValueError('旅程ID与目录不同步')
    destination=inside(root,'travel/destinations',stable_id(trip['destination_id']))
    info=read(destination/'destination.json')
    return folder,trip,destination,info


def inspect_trip(root,key):
    folder,trip,destination,info=trip_context(root,key)
    entries=read(folder/'selection.json')['items']
    seen=set()
    for entry in entries:
        place_id=stable_id(entry['place_id'])
        if place_id in seen or not inside(root,str(destination/'places'),place_id,'place.json').is_file():
            raise ValueError('筛选表有重复或未知景点')
        if entry['status'] not in ('candidate','shortlist','excluded'):
            raise ValueError('筛选意向须为 candidate/shortlist/excluded')
        seen.add(place_id)
    days=[]
    for path in sorted((folder/'days').glob('*.json')):
        day=read(path)
        if day.get('simulation') is not False:
            raise ValueError('正式旅行资料不能使用模拟场景')
        if day.get('status') not in ('draft','ready'):
            raise ValueError('日计划状态须为 draft 或 ready')
        for stop in day['stops']+day['cancelled']:
            place_id=stable_id(stop['place_id'])
            if not inside(root,str(destination/'places'),place_id,'place.json').is_file():
                raise ValueError('日计划引用未知景点')
        excluded={x['place_id'] for x in entries if x['status']=='excluded'}
        if excluded & {x['place_id'] for x in day['stops']}:
            raise ValueError('日计划与筛选排除冲突，请先核对决定')
        days.append({'id':path.stem,'status':day['status'],'stops':len(day['stops'])})
    return {'trip':key,'destination':info['name'],'days':days,'planned_stops':sum(d['stops'] for d in days),'selection_count':len(entries),'note':'结构检查不是来源重查，也不是道路或开放时间验证'}


def day_context(root,key,day_id):
    inspect_trip(root,key)
    stable_id(day_id)
    folder,trip,destination,info=trip_context(root,key)
    day=read(inside(root,str(folder/'days'),day_id+'.json'))
    if day['status']!='ready' or not day['stops']:
        raise ValueError('日计划仍是草稿；先确认景点、时段并设 status=ready')
    if len(day['stops'])>3:
        raise ValueError('当前静态地图仅验收最多三个活动景点；扩展前需修改并验图')
    if day.get('timezone')!=info['timezone']:
        raise ValueError('日计划时区与目的地不同步')
    if trip.get('budget_currency')!='MYR':
        raise ValueError('当前费用生成器仅支持MYR已知门票小计；其他币种需扩展')
    if 'travel' in day:
        raise ValueError('酒店、机场与交通方式只在 trip.json 维护，日计划不重复存 travel')
    ids={s['place_id'] for s in day['stops']+day['cancelled']}
    places={i:read(inside(root,str(destination/'places'),stable_id(i),'place.json')) for i in sorted(ids)}
    anchors={}
    mode=trip.get('transport_mode')
    if mode=='driving':
        for field in ('hotel_id','airport_id'):
            if not trip.get(field):
                raise ValueError('汽车道路模式需要明确酒店与机场；未知时保持草稿')
            anchor_id=stable_id(trip[field])
            anchors[anchor_id]=read(inside(root,str(destination/'anchors'),anchor_id,'anchor.json'))
        day['travel']={'hotel_id':trip['hotel_id'],'airport_id':trip['airport_id'],'profile':'driving','buffer_minutes':trip.get('transfer_buffer_minutes',15),'max_snap_m':250}
    elif mode!='schematic':
        raise ValueError('先明确交通方式：driving 或仅位置示意 schematic；不自动降级')
    return folder,places,anchors,day


def build_day(root,key,day_id,check_only=False):
    folder,places,anchors,day=day_context(root,key,day_id)
    import travel_sync as sync
    out=inside(root,str(folder/'generated'),day_id)
    cache=inside(root,str(folder/'cache/routes'))
    if not check_only:
        # Validate a complete candidate before replacing views or pruning old ones.
        out.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix=f'.{day_id}-',dir=out.parent) as staging:
            stage=Path(staging)
            sync.build(places,day,stage,anchors=anchors or None,route_cache=cache)
            current=sync.check(places,day,stage,anchors=anchors or None,route_cache=cache)
            old=read(out/'manifest.json')['files'] if (out/'manifest.json').is_file() else {}
            obsolete=[]
            for name in set(old)-set(current['files']):
                allowed=re.fullmatch(r'(?:itinerary\.md|candidates\.md|anchors\.md|routing\.json|maps/(?:route\.(?:html|geojson)|overview\.png)|places/[a-z0-9-]+/(?:README\.md|maps/(?:route\.(?:html|geojson)|overview\.png)))',name)
                if not allowed:
                    raise ValueError('旧清单包含非生成文件路径，停止清理')
                target=inside(out,name)
                if target.is_file():
                    if hashlib.sha256(target.read_bytes()).hexdigest()!=old[name]:
                        raise ValueError(f'旧生成文件已被手改，请先保存个人内容再重建：{name}')
                    obsolete.append(target)
            for name in current['files']:
                target=inside(out,name)
                target.parent.mkdir(parents=True,exist_ok=True)
                shutil.copy2(stage/name,target)
            for target in obsolete:
                target.unlink()
            shutil.copy2(stage/'manifest.json',out/'manifest.json')
    result=sync.check(places,day,out,anchors=anchors or None,route_cache=cache)
    site=inside(root,str(folder/'site'),day_id)
    if check_only:
        for name in ('route.html','route.geojson','overview.png'):
            if not (site/name).is_file() or (site/name).read_bytes()!=(out/'maps'/name).read_bytes():
                raise ValueError('预览副本不同步，请重新 build')
    else:
        site.mkdir(parents=True,exist_ok=True)
        for name in ('route.html','route.geojson','overview.png'):
            shutil.copy2(out/'maps'/name,site/name)
        links=[f'<li><a href="{html.escape(p.name)}/route.html">{html.escape(p.name)}</a></li>' for p in sorted(site.parent.iterdir()) if p.is_dir() and (p/'route.html').exists()]
        (site.parent/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>旅程地图</title><h1>已生成的日计划地图</h1><p>修改源数据后需重新 build；地图不代表实际到访。</p><ul>'+''.join(links)+'</ul>',encoding='utf-8')
    return {'ok':True,'revision':day['revision'],'active':result['active_ids'],'files':len(result['files']),'output':str(out)}


def build_web(root,key,check_only=False):
    status=inspect_trip(root,key)
    folder,trip,destination,info=trip_context(root,key)
    ready=[]
    for day in status['days']:
        if day['status']=='ready':
            build_day(root,key,day['id'],check_only=True)
            ready.append(day['id'])
    import discovery_web
    return discovery_web.build(Path(root),key,folder,trip,destination,info,ready,check_only)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    sub=parser.add_subparsers(dest='command',required=True)
    new=sub.add_parser('new-project'); new.add_argument('path')
    dest=sub.add_parser('destination'); dest.add_argument('id'); dest.add_argument('--name',required=True); dest.add_argument('--timezone',required=True)
    trip=sub.add_parser('trip'); trip.add_argument('id'); trip.add_argument('--destination',required=True); trip.add_argument('--title',required=True)
    for command in ('inspect','build','check','fetch','serve','web','web-check','web-serve'):
        cmd=sub.add_parser(command); cmd.add_argument('--trip',required=True)
        if command in ('build','check','fetch'): cmd.add_argument('--day',required=True)
        if command=='fetch': cmd.add_argument('--refresh',action='store_true')
        if command in ('serve','web-serve'): cmd.add_argument('--port',type=int,default=8765)
    args=parser.parse_args()
    try:
        if args.command=='new-project': result={'created':str(init_project(args.path))}
        elif args.command=='destination': result={'created':str(create_destination(ROOT,args.id,args.name,args.timezone))}
        elif args.command=='trip': result={'created':str(create_trip(ROOT,args.id,args.destination,args.title))}
        elif args.command=='inspect': result=inspect_trip(ROOT,args.trip)
        elif args.command in ('build','check'): result=build_day(ROOT,args.trip,args.day,check_only=args.command=='check')
        elif args.command in ('web','web-check'): result=build_web(ROOT,args.trip,check_only=args.command=='web-check')
        elif args.command=='web-serve':
            build_web(ROOT,args.trip,check_only=True)
            from serve_maps import serve
            serve(inside(ROOT,'docs/site'),args.port)
            return
        elif args.command=='fetch':
            folder,places,anchors,day=day_context(ROOT,args.trip,args.day)
            if not day.get('travel'): raise ValueError('示意图模式不查询道路')
            from fetch_road_routes import fetch_routes
            fetch_routes(places,anchors,[day],inside(ROOT,str(folder/'cache/routes')),args.refresh)
            result={'ok':True,'note':'道路缓存已准备；随后运行 build'}
        else:
            folder,_,_,_=trip_context(ROOT,args.trip)
            from serve_maps import serve
            serve(inside(ROOT,str(folder/'site')),args.port)
            return
        print(json.dumps(result,ensure_ascii=False,indent=2))
    except (ValueError,FileExistsError,FileNotFoundError,KeyError,TypeError) as exc:
        parser.exit(2,f'无法完成：{exc}\n')


if __name__=='__main__':
    main()
