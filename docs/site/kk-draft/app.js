/* The page is a view: browser interactions never mutate trip source files. */
(() => {
  'use strict';
  const data = JSON.parse(document.getElementById('travel-data').textContent);
  const $ = id => document.getElementById(id);
  const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const cards = [...document.querySelectorAll('.place-card')];
  const markers = new Map();
  let map = null, tileOK = false;
  const anchors = data.geo.features.filter(f => f.properties.kind !== 'place');
  if (window.L && data.geo.features.length) {
    map = L.map('map', {scrollWheelZoom:false});
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {maxZoom:19, attribution:'&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>'})
      .on('tileload', () => {tileOK = true; $('map-status').textContent = '底图已加载。点击点位查看来源与精度；酒店、机场、码头始终保留。';})
      .on('tileerror', () => {if (!tileOK) $('map-status').textContent = '底图暂时不可用；点位仍可查看，或展开离线位置示意图。';}).addTo(map);
    data.geo.features.forEach(feature => {
      const p = feature.properties, [lon,lat] = feature.geometry.coordinates;
      const marker = L.marker([lat,lon], {icon:L.divIcon({className:'reference-marker',iconSize:[34,34],iconAnchor:[17,17],html:`<span class="point-label ${p.kind !== 'place' ? 'anchor':''}" style="--marker:${p.color}">${escapeHTML(p.label)}</span>`}),title:p.name,zIndexOffset:p.kind==='hotel'?1000:0});
      const distance = typeof p.distance_km === 'number' ? `<p>距酒店直线约 ${p.distance_km} km · 非交通距离</p>`:'';
      marker.bindPopup(`<b>${escapeHTML(p.label)} ${escapeHTML(p.name)}</b>${distance}<p>${escapeHTML(p.coordinate_precision)}</p><p>${escapeHTML(p.reason || p.notes || '')}</p><a href="${escapeHTML(p.coordinate_source)}" target="_blank" rel="noopener noreferrer">点位来源 ↗</a>${p.kind==='place'?`<p><a href="#${escapeHTML(p.id)}">查看景点卡片 ↓</a></p>`:''}`,{maxWidth:310}).addTo(map);
      markers.set(p.id,marker);
    });
    L.control.scale({imperial:false}).addTo(map);
    if(data.bounds) map.fitBounds(data.bounds); else map.fitBounds(data.geo.features.map(f=>[f.geometry.coordinates[1],f.geometry.coordinates[0]]),{maxZoom:14,padding:[30,30]});
  } else {
    $('map-status').textContent = '地图库未加载或没有点位；景点卡片与离线位置示意图仍可浏览。';
    $('map').style.height = '90px';
    $('map').textContent = '可展开下方离线位置示意图，或查看景点卡片中的点位来源。';
  }
  function filter() {
    const q=$('search').value.trim().toLocaleLowerCase(), region=$('region').value, category=$('category').value, status=$('status').value;
    let count=0;
    cards.forEach(card=>{
      const show=(!q||card.textContent.toLocaleLowerCase().includes(q))&&(!region||card.dataset.region===region)&&(!category||card.dataset.category===category)&&(!status||card.dataset.status===status);
      card.hidden=!show; if(show)count++;
      const marker=markers.get(card.id);
      if(map&&marker){if(show&&!map.hasLayer(marker))marker.addTo(map);if(!show&&map.hasLayer(marker))map.removeLayer(marker);}
    });
    $('results').textContent=`显示 ${count} / ${cards.length} 项候选`; $('empty').hidden=count!==0;
  }
  ['search','region','category','status'].forEach(id=>$(id).addEventListener(id==='search'?'input':'change',filter));
  $('clear').addEventListener('click',()=>{['search','region','category','status'].forEach(id=>$(id).value='');filter();});
  $('nearby').addEventListener('click',()=>{if(map&&data.bounds)map.fitBounds(data.bounds);});
  $('all-map').addEventListener('click',()=>{if(map)map.fitBounds([...markers.values()].filter(m=>map.hasLayer(m)).map(m=>m.getLatLng()),{padding:[35,35],maxZoom:14});});
  $('hotel-map').addEventListener('click',()=>{const hotel=anchors.find(a=>a.properties.kind==='hotel');if(map&&hotel){const marker=markers.get(hotel.properties.id);map.setView(marker.getLatLng(),15);marker.openPopup();}});
  document.querySelectorAll('.locate').forEach(button=>button.addEventListener('click',()=>{const marker=markers.get(button.dataset.place);if(map&&marker){$('map-section').scrollIntoView();map.setView(marker.getLatLng(),marker.feature?.properties?.kind==='place'?14:14);marker.openPopup();}else{$('map-status').textContent='该点尚无已核实坐标，或地图库未加载；请看卡片来源。';$('map-section').scrollIntoView();}}));
  function compare() {
    const chosen=[...document.querySelectorAll('.compare:checked')].map(c=>data.places.find(p=>p.id===c.value));
    $('picked-count').textContent=chosen.length;
    $('selection-note').value=chosen.length?`我的${data.destinationName}初筛意向（尚未排日程）：\n`+chosen.map(p=>`- ${p.label} ${p.name}（${p.region_name}）`).join('\n')+'\n\n希望继续比较：\n可以排除的类型：':'';
  }
  document.querySelectorAll('.compare').forEach(c=>c.addEventListener('change',compare));
  $('copy').addEventListener('click',async()=>{if(!$('selection-note').value){$('copy-status').textContent='先勾选希望比较的景点。';return;}try{await navigator.clipboard.writeText($('selection-note').value);$('copy-status').textContent='已复制。发送到对话后再确认正式选择。';}catch{ $('selection-note').select();$('copy-status').textContent='请手动复制选中的文字。';}});
})();
