"""Deterministic, read-only discovery views from formal travel sources."""
import hashlib
import html
import json
import math
from pathlib import Path
import re
import shutil

ASSETS=Path(__file__).resolve().parents[1]/'assets/discovery'
COLORS=['#18796c','#c48334','#657f45','#357c99','#8e6593','#676f9d','#a26452']
STATUS={'candidate':'待筛选','shortlist':'优先考虑','excluded':'本次排除'}
def read(p): return json.loads(p.read_text('utf-8-sig'))
def dump(v): return json.dumps(v,ensure_ascii=False,indent=2)+'\n'
def esc(v): return html.escape(str(v),quote=True)
def digest(b): return hashlib.sha256(b).hexdigest()
def safe_url(url): return url if str(url).startswith(('https://','http://')) else '#'
def coord(record):
    c=record.get('coordinates')
    return (isinstance(c,list) and len(c)==2 and all(isinstance(x,(int,float)) and not isinstance(x,bool) and math.isfinite(x) for x in c) and -180<=c[0]<=180 and -90<=c[1]<=90)
def distance(a,b):
    x1,y1,x2,y2=map(math.radians,[*a,*b])
    v=math.sin((y2-y1)/2)**2+math.cos(y1)*math.cos(y2)*math.sin((x2-x1)/2)**2
    return round(6371*2*math.asin(min(1,math.sqrt(v))),1)
def inline(text):
    text=esc(text)
    text=re.sub(r'\[([^\]]+)\]\((https?://[^\s)]+)\)',r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>',text)
    return re.sub(r'\*\*(.+?)\*\*',r'<strong>\1</strong>',text)
def markdown(text):
    # This project uses a small safe Markdown subset; never execute raw HTML.
    parts=[]
    for block in re.split(r'\n\s*\n',text.strip()):
        if block.startswith('# '): continue
        if block.startswith('## '): parts.append('<h3>'+inline(block[3:])+'</h3>')
        elif block.startswith('- '): parts.append('<ul>'+''.join('<li>'+inline(x[2:])+'</li>' for x in block.splitlines() if x.startswith('- '))+'</ul>')
        else: parts.append('<p>'+inline(block).replace('\n','<br>')+'</p>')
    return ''.join(parts)

def svg_map(features,regional=False):
    """Coordinate diagram only: never fabricate coastlines, roads or routes."""
    points=[f for f in features if regional or (f['properties'].get('distance_km') or 0)<30]
    if regional:
        points=[f for f in points if f['properties']['kind']=='hotel' or (f['properties'].get('distance_km') or 0)>=30]
    if not points: return '<svg xmlns="http://www.w3.org/2000/svg"><text x="10" y="30">暂无已核实点位</text></svg>'
    cs=[f['geometry']['coordinates'] for f in points]
    xmin,xmax=min(p[0] for p in cs)-.018,max(p[0] for p in cs)+.018
    ymin,ymax=min(p[1] for p in cs)-.018,max(p[1] for p in cs)+.018
    scale=min(620/(xmax-xmin),450/(ymax-ymin))
    def xy(c): return 55+(c[0]-xmin)*scale,510-(c[1]-ymin)*scale
    s=['<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="610" viewBox="0 0 1100 610" role="img">', '<rect width="1100" height="610" fill="#f3f5f0"/>','<g font-family="Microsoft YaHei, sans-serif" fill="#203d38">',f'<text x="32" y="35" font-size="23">{("区域全景" if regional else "市区与近郊")} · 经纬度位置示意</text>','<text x="32" y="578" font-size="14">无道路与海岸线；编号仅供检索，非游览顺序。北↑ 东→　© OpenStreetMap contributors；其他点源见网页。</text>']
    for n in range(6):
        x=55+124*n; y=60+90*n
        s.extend([f'<path d="M{x} 60V510 M55 {y}H675" stroke="#d4ded7"/>'])
    for i,f in enumerate(points):
        p=f['properties']; x,y=xy(f['geometry']['coordinates']); label=p['label']
        s.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="8" fill="{p["color"]}" stroke="white" stroke-width="2"/><text x="{x+10:.2f}" y="{y-7:.2f}" font-size="13">{esc(label)}</text>')
        s.append(f'<text x="710" y="{68+i*25}" font-size="14" fill="{p["color"]}">{esc(label+"  "+p["name"])}</text>')
    s.append('</g></svg>')
    return ''.join(s)

def build(root,key,folder,trip,destination,info,ready,check_only=False):
    assets_dir=root/'skills/travel-workflow/assets/discovery'
    conf_path=destination/'discovery.json'
    config=read(conf_path) if conf_path.exists() else {}
    selected=read(folder/'selection.json')['items']
    selection={x['place_id']:x for x in selected}
    order=[x for x in config.get('display_order',[]) if x in selection]
    order+=sorted(set(selection)-set(order))
    if len(order)!=len(set(order)): raise ValueError('候选展示顺序重复')
    regions=config.get('regions',{})
    palette={r:COLORS[i%len(COLORS)] for i,r in enumerate(regions)}
    source_paths=[folder/'trip.json',folder/'selection.json',folder/'requirements.md',destination/'destination.json',destination/'overview.md']
    if conf_path.exists(): source_paths.append(conf_path)
    source_paths+=sorted((folder/'days').glob('*.json'))
    anchors=[]
    for a in dict.fromkeys([trip.get('hotel_id'),trip.get('airport_id')]+config.get('reference_anchors',[])):
        if a:
            path=destination/'anchors'/a/'anchor.json'; source_paths.append(path); anchors.append(read(path))
    hotel=next((a for a in anchors if a['id']==trip.get('hotel_id')),None)
    features=[]; cards=[]; summary_rows=[]; places=[]
    for index,id in enumerate(order,1):
        path=destination/'places'/id/'place.json'; source_paths.append(path); p=read(path)
        d=p.get('discovery',{}); region=d.get('region','other'); status=selection[id]['status']
        label=f'P{index:02d}'; color='#89938c' if status=='excluded' else palette.get(region,COLORS[0])
        km=distance(hotel['coordinates'],p['coordinates']) if hotel and coord(hotel) and coord(p) else None
        props={'id':id,'label':label,'name':p['name'],'local_name':p.get('local_name',''),'region':region,'region_name':regions.get(region,'待分区'),'category':p.get('category','待分类'),'kind':'place','status':status,'reason':selection[id].get('reason',''),'color':color,'distance_km':km,'coordinate_precision':p.get('coordinate_precision','待确认'),'coordinate_source':safe_url(p.get('coordinate_source',''))}
        places.append(props)
        if coord(p): features.append({'type':'Feature','geometry':{'type':'Point','coordinates':p['coordinates']},'properties':props})
        dist=f'距酒店直线约 {km:g} km' if km is not None else '坐标或酒店位置待补充'
        details=''.join(f'<div class="fact"><dt>{title}</dt><dd>{inline(p.get(field,"待细化"))}</dd></div>' for title,field in [('开放与预约','access'),('费用口径','ticket_basis'),('交通判断','transport'),('食物方向','food'),('购物方向','shopping')])
        refs=' · '.join(f'<a href="{esc(safe_url(s["url"]))}" target="_blank" rel="noopener noreferrer">{esc(s["title"])}</a>' for s in p.get('sources',[]))
        cards.append(f'''<article class="place-card" id="{esc(id)}" data-region="{esc(region)}" data-category="{esc(props['category'])}" data-status="{status}">
<div class="card-top"><span class="place-number" style="--accent:{color}">{label}</span><span>{esc(props['region_name'])} · {esc(STATUS[status])}</span><label class="compare-label"><input type="checkbox" class="compare" value="{esc(id)}"> 比较</label></div>
<h3>{esc(p['name'])}</h3><p class="local-name">{esc(p.get('local_name',''))}</p><p>{inline(p.get('summary',''))}</p>
<div class="chips"><span>{esc(props['category'])}</span><span>{esc(d.get('effort','待确认'))}</span></div>
<p class="fit"><b>怎么选</b> {inline(p.get('fit','待确认'))}</p><p class="meta">{esc(p.get('duration_advice','时长待确认'))}<br>{esc(dist)} · 非交通距离</p>
<p class="caveat">{inline(d.get('caveat','信息待继续核实'))}</p><details><summary>查看费用、限制与来源</summary><dl>{details}</dl><p class="sources">核查：{esc(p.get('checked_at','未知'))}<br>{refs}</p><p class="sources">坐标：{esc(p.get('coordinate_precision','待确认'))} · <a href="{esc(safe_url(p.get('coordinate_source','')))}" target="_blank" rel="noopener noreferrer">点位来源</a></p></details><button class="locate" data-place="{esc(id)}">在地图中查看</button></article>''')
        summary_rows.append('| '+' | '.join(str(x).replace('|','／').replace('\n',' ') for x in [label,p['name'],props['region_name'],STATUS[status],p.get('duration_advice','待定'),dist,p.get('fit',''),d.get('caveat','')])+' |')
    for a in anchors:
        if not coord(a): continue
        kind='hotel' if a['id']==trip.get('hotel_id') else a.get('kind','anchor')
        props={'id':a['id'],'label':{'hotel':'H','airport':'A','jetty':'J'}.get(kind,'•'),'name':a['name'],'kind':kind,'color':'#b7682d' if kind=='hotel' else '#334a50','status':'reference','notes':a.get('notes',''),'coordinate_precision':a.get('coordinate_precision','待确认'),'coordinate_source':safe_url(a.get('coordinate_source','')),'distance_km':distance(hotel['coordinates'],a['coordinates']) if hotel and coord(hotel) else None}
        features.append({'type':'Feature','geometry':{'type':'Point','coordinates':a['coordinates']},'properties':props})
    geo={'type':'FeatureCollection','name':info['name']+'认知参考点','metadata':{'purpose':'候选位置认知；无具体日程、道路或船行路线','distance_basis':'从酒店到代表点的球面直线距离，非交通距离','point_attribution':'© OpenStreetMap contributors / ODbL；其他来源逐点标明'},'features':features}
    outputs={'recognition.geojson':dump(geo).encode('utf8'),'nearby.svg':svg_map(features).encode('utf8'),'regional.svg':svg_map(features,True).encode('utf8')}
    day_sections=[]
    for day_id in ready:
        generated=folder/'generated'/day_id
        manifest=read(generated/'manifest.json')
        for name in manifest['files']:
            path=(generated/name).resolve()
            if not path.is_relative_to(generated.resolve()): raise ValueError('日计划输出路径越界')
            source_paths.append(path); outputs[f'days/{day_id}/{name}']=path.read_bytes()
        source_paths.append(generated/'manifest.json')
        day_sections.append(f'<details><summary>{esc(day_id)} · 已生成攻略</summary>{markdown((generated/"itinerary.md").read_text("utf8"))}<a href="days/{esc(day_id)}/maps/route.html">打开当日路线地图</a></details>')
    assets=sorted(p for p in assets_dir.iterdir() if p.is_file())
    source_paths+=assets+[root/'skills/travel-workflow/scripts/discovery_web.py',root/'scripts/travel.py']
    sources={p.relative_to(root).as_posix():digest(p.read_bytes()) for p in source_paths}
    region_options=''.join(f'<option value="{esc(k)}">{esc(v)}</option>' for k,v in regions.items())
    cat_options=''.join(f'<option>{esc(c)}</option>' for c in sorted({p['category'] for p in places}))
    hotel_html=(f'<span class="eyebrow">YOUR BASE / 酒店参照</span><h2>{esc(hotel["name"])}</h2><p>{esc(hotel.get("address",""))}</p><a href="{esc(safe_url(hotel.get("source","")))}" target="_blank" rel="noopener noreferrer">核对酒店官网 ↗</a>' if hotel else '<h2>酒店尚未确定</h2><p>可先了解候选，之后补充住宿位置。</p>')
    template=(assets_dir/'index.html').read_text('utf8')
    values={'TITLE':esc(info['name']),'HEADLINE':esc(config.get('title','目的地认知与景点筛选')),'SUBTITLE':esc(config.get('subtitle','候选不等于日程，先比较体验与限制。')),'COUNT':str(len(order)),'REGION_COUNT':str(len(regions)),'DAY_COUNT':str(len(ready)),'CHECKED':esc(config.get('checked_at','见各来源')),'HOTEL':hotel_html,'REGION_OPTIONS':region_options,'CATEGORY_OPTIONS':cat_options,'CARDS':''.join(cards),'OVERVIEW':markdown((destination/'overview.md').read_text('utf8')),'PROMPTS':''.join('<li>'+inline(t)+'</li>' for t in config.get('comparison_prompts',[])),'DAY_VIEWS':''.join(day_sections) or '<p>尚未安排具体日期、顺序或时段。</p>','DATA':json.dumps({'geo':geo,'places':places,'bounds':config.get('map_nearby_bounds'),'trip':key,'destinationName':info['name']},ensure_ascii=False).replace('<','\\u003c')}
    for token,value in values.items(): template=template.replace('{{'+token+'}}',value)
    outputs['index.html']=template.encode('utf8')
    for name in ('app.js','style.css'): outputs[name]=(assets_dir/name).read_bytes()
    candidates=('# '+info['name']+'主要景点候选\n\n由 `web` 命令从景点知识和本次筛选源生成。编号是检索编号，不是日程；时间为规划建议，距离为酒店到代表点的直线距离。\n\n| 编号 | 候选 | 区域 | 本次意向 | 时间投入 | 酒店参照 | 适合与取舍 | 主要限制 |\n|---|---|---|---|---|---|---|---|\n'+'\n'.join(summary_rows)+'\n').encode('utf8')
    out=root/'docs/site'/key
    manifest={'schema_version':1,'trip':key,'sources':sources,'files':{n:digest(b) for n,b in outputs.items()},'companions':{'candidates.md':digest(candidates),'recognition.geojson':digest(outputs['recognition.geojson'])}}
    if check_only:
        if not (out/'manifest.json').is_file() or read(out/'manifest.json')!=manifest: raise ValueError('网页过期或来源不同步，请运行 web')
        for n,b in outputs.items():
            if not (out/n).is_file() or (out/n).read_bytes()!=b: raise ValueError('网页或地图不同步，请运行 web')
        if (folder/'candidates.md').read_bytes()!=candidates or (destination/'maps/recognition.geojson').read_bytes()!=outputs['recognition.geojson']: raise ValueError('候选表或地图副本不同步')
    else:
        out.mkdir(parents=True,exist_ok=True)
        old=read(out/'manifest.json').get('files',{}) if (out/'manifest.json').is_file() else {}
        obsolete=[]
        for name in set(old)-set(outputs):
            path=(out/name).resolve()
            if not path.is_relative_to(out.resolve()): raise ValueError('旧网页清单路径越界')
            if path.is_file():
                if digest(path.read_bytes())!=old[name]: raise ValueError('旧网页输出已被手改，请先保存后重建')
                obsolete.append(path)
        for n,b in outputs.items():
            p=out/n; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(b)
        for path in obsolete: path.unlink()
        (out/'manifest.json').write_text(dump(manifest),'utf8')
        (folder/'candidates.md').write_bytes(candidates)
        (destination/'maps').mkdir(exist_ok=True)
        (destination/'maps/recognition.geojson').write_bytes(outputs['recognition.geojson'])
        links=''.join(f'<li><a href="{esc(p.name)}/index.html">{esc(p.name)}</a></li>' for p in sorted(out.parent.iterdir()) if p.is_dir() and (p/'index.html').is_file())
        (out.parent/'index.html').write_text('<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>旅行攻略</title><h1>旅行攻略浏览</h1><ul>'+links+'</ul></html>','utf8')
    return {'ok':True,'candidates':len(order),'mapped_points':len(features),'ready_days':len(ready),'output':str(out/'index.html'),'check_only':check_only}
