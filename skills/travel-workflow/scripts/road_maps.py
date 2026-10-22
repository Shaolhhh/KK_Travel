"""Folium road layers and an offline geographically scaled route drawing."""
import html
import json
import math
from pathlib import Path
import folium
from branca.element import MacroElement,Template
from PIL import Image,ImageDraw
from map_styles import font,stable_ids
from road_routes import GROUPS

COLORS={'arrival':'#3769b7','day':'#087e86','departure':'#8755a6'}


class ResponsiveFit(MacroElement):
    _template=Template('''{% macro script(this, kwargs) %}
    (function(){
      const map = {{this._parent.get_name()}};
      const bounds = {{this.bounds|tojson}};
      const details = document.getElementById('trip-details');
      if(window.innerWidth < 700 && details) details.open = false;
      function fitTrip(){
        const small = window.innerWidth < 700;
        map.invalidateSize();
        map.fitBounds(bounds,{paddingTopLeft:small?[25,75]:[330,90],paddingBottomRight:[35,40]});
      }
      L.control.zoom({position:'bottomright'}).addTo(map);
      fitTrip();
      window.addEventListener('resize',fitTrip);
    })();
    {% endmacro %}''')
    def __init__(self,bounds):
        super().__init__()
        self._name='ResponsiveFit'
        self.bounds=bounds


def interactive(data,title,target):
    points=[f for f in data['features'] if f['geometry']['type']=='Point']
    lines=[f for f in data['features'] if f['properties'].get('kind')=='road']
    m=folium.Map(location=points[0]['geometry']['coordinates'][::-1],zoom_start=13,tiles='OpenStreetMap',control_scale=True,zoom_control=False)
    groups={key:folium.FeatureGroup(name=label,show=True).add_to(m) for key,label in GROUPS.items()}
    anchor_layer=folium.FeatureGroup(name='酒店与机场',show=True).add_to(m)
    for f in points:
        p=f['properties']
        role=p['kind']
        number=p['order']
        label=f"{number}. {p['name']}"+(f" {p['start']}–{p['end']}" if 'start' in p else '')
        color='#b16a24' if role=='hotel' else COLORS['departure'] if role=='airport' else COLORS['day']
        content=html.escape(label)+'<br>'+html.escape(p.get('note','地图代表点；以现场合法入口及接送点为准'))
        folium.Marker(f['geometry']['coordinates'][::-1],tooltip=label,popup=folium.Popup(content,max_width=320),icon=folium.DivIcon(html=f'<div class="trip-marker" data-place-id="{html.escape(p["place_id"])}" style="background:{color};color:white;width:30px;height:30px;border:2px solid white;border-radius:50%;text-align:center;line-height:26px;font-weight:700;box-shadow:0 1px 5px #555">{number}</div>',icon_size=(30,30),icon_anchor=(15,15))).add_to(anchor_layer if role in ('hotel','airport') else groups['day'])
    for f in lines:
        p=f['properties']
        group=p['group']
        label=f"{GROUPS[group]} · {p['distance_m']/1000:.2f} km · 约{math.ceil(p['duration_s']/60)}分钟（路网估算）"
        popup=html.escape(label)+f"<br>起/终点吸附偏移：{p['snap_m'][0]:.1f} / {p['snap_m'][1]:.1f}米<br>不含实时交通、候车及机场手续"
        folium.PolyLine([c[::-1] for c in f['geometry']['coordinates']],color=COLORS[group],weight=5 if group=='day' else 4,opacity=.85,tooltip=label,popup=folium.Popup(popup,max_width=350)).add_to(groups[group])
    all_coords=[c for f in lines for c in f['geometry']['coordinates']]
    folium.LayerControl(collapsed=True,position='topright').add_to(m)
    ResponsiveFit([c[::-1] for c in all_coords]).add_to(m)
    stats=''.join(f'<div style="margin:8px 0;color:{COLORS[g]}"><b>{GROUPS[g]}</b><br>{v["distance_m"]/1000:.2f} km · 约{math.ceil(v["duration_s"]/60)}分钟</div>' for g,v in data['routing']['totals'].items())
    order=' → '.join(f"{p['properties']['order']}. {p['properties']['name']}" for p in points if p['properties']['kind']=='attraction')
    panel=f'''<aside id="trip-panel" style="position:fixed;left:14px;top:14px;z-index:999;width:292px;padding:16px;background:rgba(255,255,255,.96);border-radius:12px;box-shadow:0 3px 18px #0002;font:14px/1.55 system-ui,sans-serif">
    <details id="trip-details" open><summary style="font-size:17px;font-weight:700;cursor:pointer">{html.escape(title)}</summary><div id="revision">{html.escape(data['revision'])}</div>
    <p id="day-order">酒店 → {html.escape(order)} → 酒店</p>{stats}
    <p>日游酒店出发参考 <b>{data['routing']['hotel_departure']}</b><br>返回参考 <b>{data['routing']['hotel_return']}</b></p>
    <p>H 酒店 · A 机场 · 数字为日游顺序<br>右上角可切换日游及机场往返图层</p>
    <p style="font-size:12px;color:#53656e">车程为OSRM模型，不含实时交通与候车；机场接送日期、航班及航站楼层待确认。上下车位置需现场核对。</p>
    <a href="route.geojson" download>下载路线 GeoJSON</a> · <a href="overview.png" target="_blank">静态图</a>
    <p style="font-size:11px">道路：OSRM/FOSSGIS · 数据：© OpenStreetMap contributors / ODbL<br><a href="https://www.openstreetmap.org/fixthemap" target="_blank">纠正地图</a></p>
    </details></aside><style>@media(max-width:700px){{ #trip-panel{{width:225px!important;max-height:60vh;overflow:auto;font-size:12px!important;padding:10px!important}} #trip-panel summary{{font-size:14px!important}} }}</style>'''
    # Branca treats Element text as Jinja; CSS selectors must remain literal.
    m.get_root().html.add_child(folium.Element('{% raw %}'+panel+'{% endraw %}'))
    payload=json.dumps(data,ensure_ascii=False,sort_keys=True).replace('</','<\\/')
    m.get_root().html.add_child(folium.Element(f'<script id="travel-data" type="application/json">{payload}</script>'))
    stable_ids(m.get_root())
    target=Path(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    target.write_text(m.get_root().render(),encoding='utf-8',newline='\n')


def static(data,title,target):
    im=Image.new('RGB',(1420,1030),'#f5f4ef')
    d=ImageDraw.Draw(im)
    ink,muted='#203e48','#61757b'
    d.text((38,24),title+' · 汽车道路路线',font=font(30,True),fill=ink)
    d.text((40,72),f"{data['revision']} · 酒店与机场往返 / 景点日游",font=font(18),fill=muted)
    d.rounded_rectangle((30,120,900,930),18,fill='#eaf1ef')
    points=[f for f in data['features'] if f['geometry']['type']=='Point']
    lines=[f for f in data['features'] if f['properties'].get('kind')=='road']
    coords=[f['geometry']['coordinates'] for f in points]+[c for f in lines for c in f['geometry']['coordinates']]
    lon0=sum(c[0] for c in coords)/len(coords)
    lat0=sum(c[1] for c in coords)/len(coords)
    co=math.cos(math.radians(lat0))
    raw=[((c[0]-lon0)*111320*co,(c[1]-lat0)*111320) for c in coords]
    xmin,xmax=min(x for x,y in raw)-850,max(x for x,y in raw)+850
    ymin,ymax=min(y for x,y in raw)-500,max(y for x,y in raw)+500
    scale=min(800/(xmax-xmin),670/(ymax-ymin))
    cx,cy=(xmin+xmax)/2,(ymin+ymax)/2
    def xy(c):
        return (465+((c[0]-lon0)*111320*co-cx)*scale,525-((c[1]-lat0)*111320-cy)*scale)
    d.text((52,136),'道路几何来自OSRM · 静态图未铺街区底图',font=font(17,True),fill=ink)
    d.text((850,165),'N ↑',font=font(19,True),fill=ink)
    # Day layer is drawn last for visual separation on shared roads.
    for group in ['arrival','departure','day']:
        for line in [f for f in lines if f['properties']['group']==group]:
            path=[xy(c) for c in line['geometry']['coordinates']]
            d.line(path,fill=COLORS[group],width=5 if group=='day' else 3,joint='curve')
            j=max(1,len(path)//2)
            a,b=path[j-1],path[j]
            angle=math.atan2(b[1]-a[1],b[0]-a[0])
            d.polygon([b,(b[0]-13*math.cos(angle-.55),b[1]-13*math.sin(angle-.55)),(b[0]-13*math.cos(angle+.55),b[1]-13*math.sin(angle+.55))],fill=COLORS[group])
    for f in points:
        x,y=xy(f['geometry']['coordinates'])
        p=f['properties']
        color='#b16a24' if p['kind']=='hotel' else COLORS['departure'] if p['kind']=='airport' else COLORS['day']
        d.ellipse((x-17,y-17,x+17,y+17),fill=color,outline='white',width=3)
        d.text((x,y-1),str(p['order']),font=font(18,True),fill='white',anchor='mm')
        left=p['kind']=='hotel'
        d.text((x-25 if left else x+25,y),p['name'],font=font(19,True),fill=ink,anchor='rm' if left else 'lm')
    d.line((65,886,65+1000*scale,886),fill=ink,width=4)
    d.text((65,898),'约1 km',font=font(14),fill=muted)
    d.text((935,130),'日游顺序 · 酒店往返',font=font(24,True),fill=ink)
    daypoints=[f for f in points if f['properties']['kind']=='attraction']
    for i,f in enumerate(daypoints):
        p=f['properties']; y=185+i*92
        d.text((938,y),f"{p['order']:02d}  {p['start']}–{p['end']}",font=font(23,True),fill=COLORS['day'])
        d.text((938,y+35),p['name'],font=font(23),fill=ink)
    y=492
    for group,total in data['routing']['totals'].items():
        d.text((938,y),GROUPS[group],font=font(21,True),fill=COLORS[group])
        d.text((938,y+32),f"{total['distance_m']/1000:.2f} km / 模型约{math.ceil(total['duration_s']/60)}分钟",font=font(18),fill=ink)
        y+=90
    for i,text in enumerate(['车程不含实时拥堵、候车和机场手续','机场往返单独展示，日期待航班确认','道路吸附点不等于合法上下车点']):
        d.text((938,800+i*32),text,font=font(16),fill=muted)
    d.text((40,958),'道路：OSRM / FOSSGIS · 地图数据：© OpenStreetMap contributors / ODbL',font=font(16),fill=muted)
    d.text((40,987),'路线查询与吸附偏移详见 routing.json · 本图为规划参考，不提供实时导航',font=font(16),fill=muted)
    Path(target).parent.mkdir(parents=True,exist_ok=True)
    im.save(target)
