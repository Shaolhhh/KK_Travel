# 项目与底层生成器约定

正式项目目录、字段与常用命令以 [data-model.md](../../../docs/data-model.md) 为唯一说明；完整流程见 [workflow.md](../../../docs/workflow.md)。不要再复制一套目录或字段定义。

`assets/trip.json` 是整次旅程元数据，`assets/day.json` 是单日源文件。`scripts/travel.py` 把旅程中酒店、机场、交通引用合并到内存中的单日输入，再调用 `travel_sync.py`；不会把派生 `travel` 配置回写进日文件。

底层生成器仍支持显式路径参数：

```text
python skills/travel-workflow/scripts/travel_sync.py build --places <places目录> --trip <完整单日json> --anchors <anchors目录> --cache <道路缓存> --out <生成目录>
python skills/travel-workflow/scripts/travel_sync.py check --places <places目录> --trip <完整单日json> --anchors <anchors目录> --cache <道路缓存> --out <生成目录>
```

低层命令用于开发回归，输入中的 `travel` 为 `hotel_id`、`airport_id`、`profile=driving`、`buffer_minutes`、`max_snap_m`。正式旅程优先使用项目入口，避免绕过草稿检查、引用选择和预览同步。

道路缓存按完整请求键保存原始响应、`response_sha256`、`fetched_at` 与 URL；返回 `LineString`、正距离/时长、坐标有限且范围有效，路线端点与吸附点一致，偏移在阈值内。缺失/无效数据不回退直线；刷新时先校验候选响应再替换旧缓存。道路耗时不含实时交通与机场手续。

生成清单绑定源数据、道路响应和渲染代码。`build` 后必须 `check`；地图行为变更还需浏览器实测。静态 PNG 不含街区底图，HTML 依赖在线 OSM/CDN；不批量下载瓦片。
