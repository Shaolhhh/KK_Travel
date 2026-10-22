"""Directed OSRM road routes; all generation reads recorded responses offline."""
import hashlib
import json
import math
from pathlib import Path

ENDPOINT = 'https://routing.openstreetmap.de/routed-car/route/v1/driving/'
PROVIDER = 'OSRM / FOSSGIS (OpenStreetMap)'
GROUPS = {'arrival':'机场 → 酒店', 'day':'酒店出发的景点日游', 'departure':'酒店 → 机场'}


def hash_json(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()


def load_anchors(folder):
    anchors={}
    for file in sorted(Path(folder).glob('*/anchor.json')):
        data=json.loads(file.read_text(encoding='utf-8'))
        if data['id'] in anchors:
            raise ValueError('重复落脚点ID')
        anchors[data['id']]=data
    return anchors


def required_legs(trip):
    travel=trip['travel']
    if travel['profile']!='driving':
        raise ValueError('此道路提供方仅配置了汽车模式')
    hotel,airport=travel['hotel_id'],travel['airport_id']
    day=[hotel]+[s['place_id'] for s in trip['stops']]+[hotel]
    return [('arrival',airport,hotel)]+[('day',a,b) for a,b in zip(day,day[1:])]+[('departure',hotel,airport)]


def request_for(points,a,b):
    coords=[points[a]['coordinates'],points[b]['coordinates']]
    return {'endpoint':ENDPOINT,'profile':'driving','coordinates':coords,'overview':'full','geometries':'geojson','steps':False,'generate_hints':False}


def cache_path(folder,request):
    return Path(folder)/(hash_json(request)+'.json')


def request_url(request):
    coords=';'.join(','.join(str(n) for n in c) for c in request['coordinates'])
    return ENDPOINT+coords+'?overview=full&geometries=geojson&steps=false&generate_hints=false'


def distance_m(a,b):
    lat=math.radians((a[1]+b[1])/2)
    return math.hypot((a[0]-b[0])*math.cos(lat),a[1]-b[1])*111320


def read_leg(points,a,b,cache,max_snap=250):
    request=request_for(points,a,b)
    path=cache_path(cache,request)
    if not path.exists():
        raise ValueError(f'道路缓存缺失：{a} → {b}；先查询道路，不能回退直线')
    saved=json.loads(path.read_text(encoding='utf-8'))
    if saved['request']!=request or hash_json(saved['response'])!=saved['response_sha256']:
        raise ValueError(f'道路缓存与请求不符或已损坏：{a} → {b}')
    response=saved['response']
    if response.get('code')!='Ok' or not response.get('routes') or len(response.get('waypoints',[]))!=2:
        raise ValueError(f'道路缓存无有效路线：{a} → {b}')
    route=response['routes'][0]
    geometry=route['geometry']
    coords=geometry['coordinates']
    if geometry['type']!='LineString' or len(coords)<3 or not all(len(c)==2 and all(math.isfinite(v) for v in c) and -180<=c[0]<=180 and -90<=c[1]<=90 for c in coords):
        raise ValueError('道路几何无效或退化为直线')
    if not all(math.isfinite(route[k]) and route[k]>0 for k in ('distance','duration')):
        raise ValueError('道路距离或耗时无效')
    waypoints=response['waypoints']
    for index,waypoint in enumerate(waypoints):
        if waypoint['distance']>max_snap or distance_m(request['coordinates'][index],waypoint['location'])>max_snap:
            raise ValueError(f'道路吸附偏移过大：{a} → {b}；需核对入口')
        if distance_m(coords[0 if index==0 else -1],waypoint['location'])>5:
            raise ValueError('道路几何端点与吸附点不符')
    return {'from':a,'to':b,'geometry':geometry,'distance_m':route['distance'],'duration_s':route['duration'],
            'requested':request['coordinates'],'snapped':[w['location'] for w in waypoints],
            'snap_m':[w['distance'] for w in waypoints],'fetched_at':saved['fetched_at'],
            'request_url':saved['request_url'],'cache_hash':saved['response_sha256']}


def assemble(places,anchors,trip,cache):
    if not anchors or cache is None:
        raise ValueError('道路数据需要落脚点与道路缓存')
    if set(places)&set(anchors):
        raise ValueError('景点与落脚点ID重复')
    points={**places,**anchors}
    travel=trip['travel']
    if travel['hotel_id'] not in anchors or travel['airport_id'] not in anchors:
        raise ValueError('酒店或机场落脚点缺失')
    legs=[]
    for group,a,b in required_legs(trip):
        legs.append({'group':group,**read_leg(points,a,b,cache,travel.get('max_snap_m',250))})
    day=[leg for leg in legs if leg['group']=='day']
    buffer=travel.get('buffer_minutes',15)
    if not isinstance(buffer,(int,float)) or buffer<0:
        raise ValueError('交通缓冲必须非负')
    def minutes(value):
        h,m=map(int,value.split(':'))
        return h*60+m
    for i,(previous,next_stop) in enumerate(zip(trip['stops'],trip['stops'][1:])):
        gap=minutes(next_stop['start'])-minutes(previous['end'])
        needed=math.ceil(day[i+1]['duration_s']/60)+buffer
        if gap<needed:
            raise ValueError(f'交通时间不足：{previous["place_id"]} → {next_stop["place_id"]}；空档{gap}分钟，估算与缓冲需{needed}分钟')
    departure=minutes(trip['stops'][0]['start'])-math.ceil(day[0]['duration_s']/60)-buffer
    arrival=minutes(trip['stops'][-1]['end'])+math.ceil(day[-1]['duration_s']/60)+buffer
    if not 0<=departure<arrival<1440:
        raise ValueError('酒店出发或返回跨日；单日模板不支持')
    clock=lambda n:f'{int(n)//60:02d}:{int(n)%60:02d}'
    totals={group:{'distance_m':sum(x['distance_m'] for x in legs if x['group']==group),'duration_s':sum(x['duration_s'] for x in legs if x['group']==group)} for group in GROUPS}
    return {'provider':PROVIDER,'profile':'driving','legs':legs,'totals':totals,'hotel_departure':clock(departure),'hotel_return':clock(arrival),'buffer_minutes':buffer,'traffic':'not_live','airport_reference':anchors[travel['airport_id']]['coordinate_precision']}


def geojson(places,anchors,trip,model,version):
    features=[]
    for index,s in enumerate(trip['stops'],1):
        p=places[s['place_id']]
        features.append({'type':'Feature','id':p['id'],'geometry':{'type':'Point','coordinates':p['coordinates']},'properties':{'kind':'attraction','place_id':p['id'],'name':p['name'],'order':index,'start':s['start'],'end':s['end'],'source_digest':version}})
    for key in [trip['travel']['hotel_id'],trip['travel']['airport_id']]:
        p=anchors[key]
        features.append({'type':'Feature','id':key,'geometry':{'type':'Point','coordinates':p['coordinates']},'properties':{'kind':p['kind'],'place_id':key,'name':p['name'],'order':'H' if p['kind']=='hotel' else 'A','note':p['coordinate_precision'],'source_digest':version}})
    for i,leg in enumerate(model['legs']):
        features.append({'type':'Feature','id':f'road-{i}','geometry':leg['geometry'],'properties':{k:v for k,v in leg.items() if k!='geometry'}|{'kind':'road','source_digest':version}})
    return {'type':'FeatureCollection','source_digest':version,'revision':trip['revision'],'features':features,'routing':{k:v for k,v in model.items() if k!='legs'}}


def summary_markdown(model,points):
    rows=['## 汽车道路路线','',f'路线来源：{PROVIDER}，按有向路段分别查询。以下耗时为路网估算，不含实时拥堵、候车、停车、上下车与机场手续。','', '| 分段 | 起点 → 终点 | 道路距离 | 模型车程 |','|---|---|---|---|']
    for leg in model['legs']:
        rows.append(f'| {GROUPS[leg["group"]]} | {points[leg["from"]]["name"]} → {points[leg["to"]]["name"]} | {leg["distance_m"]/1000:.2f} km | 约{math.ceil(leg["duration_s"]/60)}分钟 |')
    rows.extend(['','各段分钟数向上取整；汇总以原始秒数相加后取整，可能与逐段显示值之和略有差别。',''])
    for group,total in model['totals'].items():
        rows.append(f'- {GROUPS[group]}：{total["distance_m"]/1000:.2f} km，模型车程约{math.ceil(total["duration_s"]/60)}分钟。')
    rows.extend(['',f'日游建议酒店出发 {model["hotel_departure"]}，返回参考 {model["hotel_return"]}；每段另留{model["buffer_minutes"]}分钟规划缓冲，不是服务方承诺。', '', '机场接送日期和航班时刻未定，往返分别展示，未排入日游当天。航站楼、到达/出发楼层和接送点须按航班确认。', '', '路线使用地图代表点吸附到可路由道路；吸附不证明该处是合法上下车点。各段偏移和来源见 routing.json。', '', '汽车/出租车费用尚未报价；道路距离与车程不能当成计费结果。'])
    return '\n'.join(rows)+'\n'
