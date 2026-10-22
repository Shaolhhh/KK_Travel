"""Generate travel views from place facts and one day's decisions; no network access."""
import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path.cwd() / ".runtime"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import folium
from PIL import Image, ImageDraw, ImageFont
from map_styles import stable_ids
import road_routes


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2)


def digest(value):
    return hashlib.sha256(value).hexdigest()


def load_places(folder):
    result = {}
    for file in sorted(Path(folder).glob("*/place.json")):
        data = json.loads(file.read_text(encoding="utf-8"))
        if data["id"] in result:
            raise ValueError("重复景点ID")
        result[data["id"]] = data
    return result


def validate(places, trip):
    if not places or not trip["stops"]:
        raise ValueError("需要至少一个景点与活动时段")
    ids = [s["place_id"] for s in trip["stops"] + trip["cancelled"]]
    if len(ids) != len(set(ids)) or set(ids) - places.keys():
        raise ValueError("未知或重复景点ID；活动与取消列表不能重叠")
    for key, place in places.items():
        if key != place["id"] or not re.fullmatch(r"[a-z0-9-]+", key):
            raise ValueError("景点ID须为稳定的小写英文与连字符")
        lon, lat = place["coordinates"]
        if not (-180 <= lon <= 180 and -90 <= lat <= 90):
            raise ValueError("坐标无效；GeoJSON使用经度、纬度顺序")
    previous_end = "00:00"
    for stop in trip["stops"]:
        if not all(re.fullmatch(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]", stop[k]) for k in ("start", "end")):
            raise ValueError("时间格式无效")
        if not previous_end <= stop["start"] < stop["end"]:
            raise ValueError("时段重叠或顺序无效")
        period = "morning" if stop["start"] < "12:00" else "afternoon"
        if stop["period"] != period:
            raise ValueError("时段标签与开始时间不同步")
        previous_end = stop["end"]


def source_digest(places, trip, anchors=None, roads=None):
    # Include generator bytes: changing a template or rule invalidates old views too.
    modules=[Path(__file__),Path(__file__).with_name('map_styles.py')]
    if roads:
        modules += [Path(__file__).with_name(name) for name in ('road_routes.py','road_maps.py')]
    return digest(encoded({"places": places, "trip": trip, "anchors":anchors,"roads":roads}).encode("utf-8") + b''.join(p.read_bytes() for p in modules))


def point_feature(p, properties):
    return {"type": "Feature", "id": p["id"], "geometry": {"type": "Point", "coordinates": p["coordinates"]}, "properties": {"place_id": p["id"], "name": p["name"], **properties}}


def route_data(places, trip, version, anchors=None, roads=None):
    if trip.get('travel'):
        if roads is None:
            raise ValueError('道路数据或道路缓存缺失')
        return road_routes.geojson(places,anchors,trip,roads,version)
    features = []
    for n, stop in enumerate(trip["stops"], 1):
        features.append(point_feature(places[stop["place_id"]], {"order": n, "start": stop["start"], "end": stop["end"], "source_digest": version}))
    for n, (a, b) in enumerate(zip(trip["stops"], trip["stops"][1:]), 1):
        features.append({"type": "Feature", "id": f"leg-{n}", "geometry": {"type": "LineString", "coordinates": [places[a["place_id"]]["coordinates"], places[b["place_id"]]["coordinates"]]}, "properties": {"from": a["place_id"], "to": b["place_id"], "kind": "schematic", "label": "游玩顺序直线示意，非道路导航", "source_digest": version}})
    return {"type": "FeatureCollection", "source_digest": version, "revision": trip["revision"], "features": features}


def write_text(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8", newline="\n")


def font(size, bold=False):
    candidates = [Path("C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc"), Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc")]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size)
    raise RuntimeError("静态图需要中文字体：Microsoft YaHei或Noto Sans CJK")


def static_map(places, stops, title, revision, target):
    im = Image.new("RGB", (1280, 880), "#f5f4ef")
    d = ImageDraw.Draw(im)
    ink, muted, teal, orange = "#203e48", "#61757b", "#147d83", "#d57940"
    d.text((42, 25), title, font=font(32, True), fill=ink)
    d.text((44, 75), f"{revision} · 计划参考 / 不代表实际到访", font=font(18), fill=muted)
    d.rounded_rectangle((35, 120, 805, 790), 18, fill="#eaf1ef")
    # Local equirectangular projection with equal metre scale on both axes.
    coords = [p["coordinates"] for p in places.values()]
    lon0 = sum(c[0] for c in coords) / len(coords)
    lat0 = sum(c[1] for c in coords) / len(coords)
    cosine = math.cos(math.radians(lat0))
    def xy(c):
        return ((c[0]-lon0)*111320*cosine, (c[1]-lat0)*111320)
    raw = [xy(c) for c in coords]
    xmin, xmax = min(p[0] for p in raw)-750, max(p[0] for p in raw)+750
    ymin, ymax = min(p[1] for p in raw)-600, max(p[1] for p in raw)+600
    scale = min(680/(xmax-xmin), 540/(ymax-ymin))
    cx, cy = (xmin+xmax)/2, (ymin+ymax)/2
    def project(c):
        x, y = xy(c)
        return (420+(x-cx)*scale, 450-(y-cy)*scale)
    step = 10 ** math.floor(math.log10(max((ymax-ymin)/111320/4, 0.0001)))
    minlat, maxlat = lat0+ymin/111320, lat0+ymax/111320
    ticks = range(math.floor(minlat/step), math.ceil(maxlat/step)+1)
    for lat in [tick*step for tick in ticks]:
        yy = project([lon0, lat])[1]
        if 155 < yy < 735:
            d.line((60, yy, 780, yy), fill="#d4dfdc", width=1)
            d.text((65, yy+4), f"{abs(lat):.3f}°{'N' if lat>=0 else 'S'}", font=font(13), fill=muted)
    d.text((64, 135), "位置与顺序示意 · 无道路底图", font=font(18, True), fill=ink)
    d.line((752, 210, 752, 168), fill=ink, width=3)
    d.polygon([(752, 160), (746, 174), (758, 174)], fill=ink)
    d.text((745, 132), "N", font=font(18, True), fill=ink)
    points = [project(places[s["place_id"]]["coordinates"]) for s in stops]
    for a, b in zip(points, points[1:]):
        length = math.dist(a, b)
        for i in range(0, int(length), 18):
            u, v = i/length, min((i+10)/length, 1)
            d.line((a[0]+(b[0]-a[0])*u, a[1]+(b[1]-a[1])*u, a[0]+(b[0]-a[0])*v, a[1]+(b[1]-a[1])*v), fill=orange, width=4)
        angle = math.atan2(b[1]-a[1], b[0]-a[0])
        m = ((a[0]+b[0])/2, (a[1]+b[1])/2)
        d.polygon([m, (m[0]-16*math.cos(angle-.5), m[1]-16*math.sin(angle-.5)), (m[0]-16*math.cos(angle+.5), m[1]-16*math.sin(angle+.5))], fill=orange)
    for n, (p, stop) in enumerate(zip(points, stops), 1):
        x, y = p
        d.ellipse((x-18, y-18, x+18, y+18), fill=teal, outline="white", width=3)
        d.text((x, y-1), str(n), font=font(20, True), anchor="mm", fill="white")
        name = places[stop["place_id"]]["name"]
        dx = -28 if x > 540 else 28
        d.text((x+dx, y), name, font=font(20, True), anchor="rm" if dx<0 else "lm", fill=ink)
        yy = 160+(n-1)*130
        d.text((840, yy), f"{n:02d}  {stop.get('start', '位置参考')}", font=font(25, True), fill=teal)
        d.text((840, yy+42), name, font=font(24, True), fill=ink)
        if stop.get("end"):
            d.text((840, yy+80), f"游览至 {stop['end']} · 规划时段", font=font(16), fill=muted)
    d.line((80, 749, 80+1000*scale, 749), fill=ink, width=4)
    d.text((80, 759), "约1 km（地理尺度）", font=font(14), fill=muted)
    for n, line in enumerate(["虚线仅表达游玩顺序", "不能用于步行或驾车导航", "道路、车费、耗时仍待核实", "代表点不是已确认的入口"]):
        d.text((840, 630+n*30), line, font=font(18), fill=muted)
    d.text((42, 815), "点位与查询日期见各景点攻略 · 地理关系图不含道路或入口验证", font=font(16), fill=muted)
    target.parent.mkdir(parents=True, exist_ok=True)
    im.save(target)


def interactive_map(data, title, target):
    points = [f for f in data["features"] if f["geometry"]["type"] == "Point"]
    locations = [f["geometry"]["coordinates"][::-1] for f in points]
    m = folium.Map(location=locations[0], zoom_start=14, tiles="OpenStreetMap", control_scale=True)
    for f, loc in zip(points, locations):
        p = f["properties"]
        number = p.get("order", "•")
        label = f"{number}. {p['name']} {p.get('start', '')}"
        folium.Marker(loc, tooltip=label, popup=folium.Popup(html.escape(label)+"<br>参考点；入口及交通待核实", max_width=260), icon=folium.DivIcon(html=f'<div style="background:#147d83;color:white;width:28px;height:28px;border-radius:50%;text-align:center;line-height:28px;font-weight:bold">{number}</div>')).add_to(m)
    for f in data["features"]:
        if f["geometry"]["type"] == "LineString":
            folium.PolyLine([c[::-1] for c in f["geometry"]["coordinates"]], color="#d57940", dash_array="8 6", weight=4, tooltip="顺序示意，非道路导航").add_to(m)
    if len(locations)>1:
        m.fit_bounds(locations, padding=(55, 55))
    banner = f'<div style="position:fixed;top:12px;left:60px;z-index:1000;background:white;padding:12px;max-width:70%;font:15px sans-serif"><b>{html.escape(title)}</b><br>虚线为顺序示意；道路交通未核实。底图和脚本需联网。<br>点击点位查看时段；坐标来源见景点攻略。</div>'
    m.get_root().html.add_child(folium.Element(banner))
    payload = encoded(data).replace("</", "<\\/")
    m.get_root().html.add_child(folium.Element(f'<script id="travel-data" type="application/json">{payload}</script>'))
    stable_ids(m.get_root())
    write_text(target, m.get_root().render())


def build(places, trip, output, anchors=None, route_cache=None):
    validate(places, trip)
    roads=road_routes.assemble(places,anchors,trip,route_cache) if trip.get('travel') else None
    out = Path(output)
    version = source_digest(places, trip,anchors,roads)
    stamp = f"<!-- source-digest: {version} -->\n"
    active = {s["place_id"]: (n,s) for n,s in enumerate(trip["stops"], 1)}
    cancelled = {s["place_id"]: s["reason"] for s in trip["cancelled"]}
    route = route_data(places, trip, version,anchors,roads)
    written = []
    def save(path, value):
        write_text(out/path, value)
        written.append(path)
    def maps(data, title, folder, stops):
        save(f"{folder}/route.geojson", encoded(data))
        if data.get('routing'):
            import road_maps
            road_maps.interactive(data,title,out/f"{folder}/route.html")
            road_maps.static(data,title,out/f"{folder}/overview.png")
        else:
            interactive_map(data, title, out/f"{folder}/route.html")
            static_map(places, stops, title, trip["revision"], out/f"{folder}/overview.png")
        written.extend([f"{folder}/route.html", f"{folder}/overview.png"])
    maps(route, trip["title"], "maps", trip["stops"])
    if roads:
        save('routing.json',encoded(roads))
        anchor_doc=stamp+'# 酒店与机场落脚点\n\n'
        for a in anchors.values():
            anchor_doc+=f"## {a['name']}\n\n{a['local_name']}\n\n{a['address']}\n\n{a['notes']}\n\n坐标：{a['coordinates']}；{a['coordinate_precision']}。\n\n[来源]({a['source']}) · [坐标来源]({a['coordinate_source']}) · 查询日期 {a['checked_at']}\n\n"
        save('anchors.md',anchor_doc)
    for key,p in places.items():
        if key in active:
            n,s = active[key]
            status = f"本次第{n}站 · {s['start']}–{s['end']} · 计划，未实际游览"
            photo = p["photo"][s["period"]]
        elif key in cancelled:
            status, photo = "本次已取消 · "+cancelled[key], "本次无拍照安排；知识资料保留。"
        else:
            status, photo = "候选，未选入本次行程", "尚未选定游览时段。"
        transport=p['transport'] if not roads else f"向司机出示 {p['local_name']}，并核对现场合法入口与上下车点。本次汽车道路指标见上方更新；公交、步行路线、实时报价和拥堵情况仍待核实。原研究资料保留在知识源中。"
        parts = [stamp+f"# {p['name']}\n", f"{p['local_name']}\n\n**{status}**\n", f"## 为什么考虑这里\n\n{p['summary']}\n\n{p['fit']}\n\n建议停留：{p['duration_advice']}\n", f"## 交通与位置\n\n{transport}\n\n坐标：{p['coordinates']}（经度、纬度）；{p['coordinate_precision']}。\n\n[位置图](maps/route.html) · [GeoJSON](maps/route.geojson)\n\n![位置参考](maps/overview.png)\n", f"## 开放与费用\n\n{p['access']}\n\n{p['ticket_basis']}\n"]
        if roads:
            link='[本次道路地图](../../maps/route.html)'
            info='本次已取消，无该景点的活动道路段。' if key in cancelled else ''
            all_points={**places,**anchors}
            for leg in roads['legs']:
                if leg['group']=='day' and key in (leg['from'],leg['to']):
                    info+=f"\n- {all_points[leg['from']]['name']} → {all_points[leg['to']]['name']}：{leg['distance_m']/1000:.2f} km，模型车程约{math.ceil(leg['duration_s']/60)}分钟。"
            parts.insert(3,'## 本次汽车交通更新\n\n'+info+'\n\n以上为本次已查询的道路数据，更新下面知识库中的交通待查状态；不含实时拥堵、候车与车费。'+link+'\n')
        for label,content in [("食物",p["food"]),("购物",p["shopping"]),("本次拍照安排",photo),("装备",p["equipment"]),("语言",p["language"]),("风土人情观察问题",p["culture_prompt"])]:
            parts.append(f"## {label}\n\n{content}\n")
        parts.append(f"## 来源与待核实\n\n查询日期：{p['checked_at']}。查询日期不等于事实生效日期；建议与事实分开理解。\n")
        for source in p["sources"]:
            parts.append(f"- [{source['title']}]({source['url']})")
        parts.append(f"- [坐标来源]({p['coordinate_source']})\n\n这是一份计划资料，不是游记。个人笔记在源目录 notes.md 中维护。\n")
        save(f"places/{key}/README.md", "\n".join(parts))
        location = {"type": "FeatureCollection", "source_digest": version, "features": [point_feature(p, {"status": status, "source_digest": version})]}
        maps(location, p["name"]+" · 位置参考", f"places/{key}/maps", [{"place_id":key}])
    rows = []
    for n,s in enumerate(trip["stops"],1):
        p = places[s["place_id"]]
        rows.append(f"| {n} | {s['start']}–{s['end']} | [{p['name']}](places/{p['id']}/README.md) | {p['photo'][s['period']]} |")
    known = sum(places[s["place_id"]]["ticket_myr"] or 0 for s in trip["stops"])
    unknown = [places[s["place_id"]]["name"] for s in trip["stops"] if places[s["place_id"]]["ticket_myr"] is None]
    plan_kind = "模拟计划" if trip["simulation"] else "旅行计划"
    date_label = trip["date"] or "未定"
    body = stamp+f"# 一日计划 · {trip['title']}\n\n版本：{trip['revision']}。{plan_kind}；旅行日期：{date_label}；未记录实际出行。时区：{trip['timezone']}。\n\n{trip['traveler_basis']}\n\n## 游玩顺序\n\n| 顺序 | 时间 | 景点 | 本次安排 |\n|---|---|---|---|\n"+"\n".join(rows)+"\n\n## 休息与转场\n\n"+"\n".join("- "+s for s in trip["breaks"])
    body += f"\n\n## 费用\n\n已知门票小计：RM{known}。**不是旅行总费用**。\n\n入场相关费用待核实：{'、'.join(unknown) or '无'}；交通、餐饮、购物与装备费用均未计入。已取消景点的参考票价不计入本次小计。\n\n## 条件与待确认\n\n"+"\n".join("- "+s for s in trip["constraints"])
    if roads:
        body+='\n\n'+road_routes.summary_markdown(roads,{**places,**anchors})+'\n[酒店与机场信息](anchors.md) · [逐段原始指标](routing.json)\n'
    map_note='实线沿OSRM汽车路网，机场往返与日游分层；上下车点仍需现场核对。' if roads else '仅为游玩顺序，未获得道路导航几何、车程或公交数据。'
    body += "\n\n## 配套地图\n\n[交互地图](maps/route.html) · [GeoJSON](maps/route.geojson)\n\n![路线位置图](maps/overview.png)\n\n"+map_note+"\n\n## 本次选择\n\n"+trip["reason"]+"\n\n取消记录："+("；".join(places[k]["name"]+"："+v.rstrip('。') for k,v in cancelled.items()) or "无")+"。\n"
    save("itinerary.md", body)
    catalog = stamp+"# 候选景点\n\n| 景点 | 类型 | 本次状态 | 适合需求 |\n|---|---|---|---|\n"
    for key,p in places.items():
        status = f"第{active[key][0]}站" if key in active else "已取消，资料保留" if key in cancelled else "候选"
        catalog += f"| [{p['name']}](places/{key}/README.md) | {p['category']} | {status} | {p['fit']} |\n"
    save("candidates.md", catalog)
    manifest = {"revision": trip["revision"], "source_digest": version, "active_ids": list(active), "cancelled_ids": list(cancelled), "known_ticket_myr": known, "files": {path:digest((out/path).read_bytes()) for path in sorted(written)}}
    save("manifest.json", encoded(manifest))
    return manifest


def check(places, trip, output, anchors=None, route_cache=None):
    validate(places, trip)
    roads=road_routes.assemble(places,anchors,trip,route_cache) if trip.get('travel') else None
    out = Path(output)
    manifest = json.loads((out/"manifest.json").read_text(encoding="utf-8"))
    version = source_digest(places, trip,anchors,roads)
    if manifest["source_digest"] != version:
        raise ValueError("输出过期：源数据或生成器已改变，尚未同步")
    expected_paths = {"itinerary.md", "candidates.md"}
    if roads:
        expected_paths.update({'routing.json','anchors.md'})
    for folder in ["maps"] + [f"places/{key}/maps" for key in places]:
        expected_paths.update(f"{folder}/{name}" for name in ("route.geojson", "route.html", "overview.png"))
    expected_paths.update(f"places/{key}/README.md" for key in places)
    if set(manifest["files"]) != expected_paths:
        raise ValueError("输出清单缺失或不同步")
    for path, expected in manifest["files"].items():
        file = out/path
        if not file.is_file() or digest(file.read_bytes()) != expected:
            raise ValueError(f"输出损坏或不同步：{path}")
    route = json.loads((out/"maps/route.geojson").read_text(encoding="utf-8"))
    if route != route_data(places, trip, version,anchors,roads):
        raise ValueError("GeoJSON不同步")
    page = (out/"maps/route.html").read_text(encoding="utf-8")
    embedded = re.search(r'<script id="travel-data" type="application/json">(.*?)</script>', page, re.S)
    if not embedded or json.loads(embedded.group(1)) != route:
        raise ValueError("HTML地图不同步")
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["build", "check"])
    parser.add_argument("--places", type=Path, required=True)
    parser.add_argument("--trip", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--anchors",type=Path)
    parser.add_argument("--cache",type=Path)
    args = parser.parse_args()
    places = load_places(args.places)
    trip = json.loads(args.trip.read_text(encoding="utf-8"))
    anchors=road_routes.load_anchors(args.anchors) if args.anchors else None
    result = (build if args.command=="build" else check)(places, trip, args.out,anchors=anchors,route_cache=args.cache)
    print(json.dumps({"ok":True,"revision":result["revision"],"active":result["active_ids"],"known_ticket_myr":result["known_ticket_myr"],"files":len(result["files"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
