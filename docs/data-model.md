# 数据约定与执行命令

真实源数据固定在 `travel/`。文件 ID 用小写英文、数字和连字符；名称和别名可变，ID 不随显示名变化。同名景点先查别名再新增。

## 唯一来源

| 内容 | 唯一维护位置 | 不要重复维护的位置 |
|---|---|---|
| 目的地名称、时区 | `destination.json` | 不在每份攻略手动修改 |
| 景点知识与核实日期 | `places/<id>/place.json` | 不手改生成的景点 README |
| 酒店/机场位置、入口与来源 | `anchors/<id>/anchor.json` | 不把地图吸附点当合法上下车点 |
| 本次酒店/机场/交通选择 | `trip.json` | 不在日计划再写 `travel` 配置 |
| 筛选意向 | `selection.json` | 不在此重复维护当天时间与顺序 |
| 当天是否安排、顺序、时间、取消 | `days/<day-id>.json` | 不用地图手改标号维持同步 |
| 为什么做选择 | `decisions.md` | 不把它当可执行日程数据 |
| 实际经历与用户表达 | `journal/` | 不从计划或模拟测试推断 |
| 按需复盘 | `reviews/` | 生成器不自动改写 |

`selection.json` 的 `items` 每条含 `place_id`、`status`、`reason`，可补 `fit`、`blockers`、`evidence`。`status` 为 `candidate`（待筛选）、`shortlist`（优先考虑）、`excluded`（本次排除）。它表达意向，`days[].stops` 才表示排入当天；排除项不能同时在活动日程中。某天取消后可仍保留为旅程备选。

## 草稿与可生成状态

新旅程创建 `day-01.json`：`status=draft`、`simulation=false`、`stops=[]`、日期未知。这是合法草稿，`inspect` 可以检查；`build` 会明确拒绝，防止默认安排景点。`ready` 表示可以生成参考攻略，不表示已预订、已出发或所有事实均已核实。

有真实决定后把日计划设为 `ready`，填入 `stops`，例如：

```json
{"place_id":"place-id","start":"09:00","end":"10:00","period":"morning"}
```

开始/结束为当地 `HH:MM`，开始早于结束，数组顺序与时间一致，上午标签用于开始时间早于 12:00 的场次。当前不支持跨午夜。取消项为 `{"place_id":"place-id","reason":"用户说明的理由"}`，不得与同日活动项重复。变更时更新 `revision`；生成器摘要另行绑定真实内容，改版本号不能跳过校验。

只有当日活动/取消引用的景点会进入该日生成器，尚未研究完成的其他候选不会阻塞。每景点知识源仍独立保留；全部候选看 `selection.json` 和目的地目录，生成的 `candidates.md` 仅是当天涉及景点的视图。

## 关键字段

- `coordinates` 为 `[longitude, latitude]`；空模板是 `[null,null]`，入选生成前必须补有来源的坐标。`coordinate_precision` 写清建筑代表点、入口或集合点。
- `checked_at` 是事实核实日期，搬迁文件不更新它。来源冲突保留原发布日期和影响，不把旧关闭公告直接解释为今天关闭。
- `ticket_myr` 为适用口径已明确的数值或 null；未知不是免费。源中可保存各票种说明，旅伴条件不明时不自动采用“非马来西亚成人”价格。当前不做多人合计、汇率或完整预算。
- `photo` 分上午/下午建议；需要夜景、精确日落窗口等能力时先扩展字段及验证，不把下午一概当日落时刻。
- `trip.json.transport_mode` 为 `driving` 或 `schematic`；初始 null，须明确后才能生成。道路模式要有 `hotel_id` 和 `airport_id`。每段 15 分钟默认缓冲只是可调规划参数，不是用户偏好或实时预测。
- 机场接送独立展示；未提供航班时不排入某天或反推起飞时间。酒店和机场标记不会因取消景点而消失。

## 命令

在项目根目录使用 Python 3.12+；本机可把 `python` 换成 README 指定的解释器。创建目录不依赖 Folium；生成地图需安装 `requirements.txt`，中文 PNG 需微软雅黑或 Noto Sans CJK。

```text
python scripts/travel.py new-project ./dist/my-travel-project
python scripts/travel.py destination destination-id --name "目的地名称" --timezone Asia/Kuching
python scripts/travel.py trip trip-id --destination destination-id --title "旅行名称"
python scripts/travel.py inspect --trip trip-id
python scripts/travel.py fetch --trip trip-id --day day-01
python scripts/travel.py build --trip trip-id --day day-01
python scripts/travel.py check --trip trip-id --day day-01
python scripts/travel.py serve --trip trip-id --port 8765
```

前三条是不同操作：`new-project` 创建独立空项目；之后在新项目里创建目的地与旅程。目标存在时拒绝覆盖。模板包不带当前旅行资料、测试夹具、道路响应、历史证据或本机依赖；无需 Git。

`fetch` 是唯一联网取道路的入口，只补缺失路段，主动更新用 `--refresh`。OSRM/FOSSGIS 响应按提供方/模式/方向/坐标缓存，往返各查；带 User-Agent，串行间隔至少 1.1 秒。无效响应先拒绝，保留已有缓存；不回退直线。刷新后需重新生成受影响日期。

`build` 先在临时目录完整生成并检查，再更新当天输出和 `site/`。旧清单中不再需要的生成文件会清理，例如切换示意图后旧的道路明细；未被清单跟踪的个人笔记不动。需清理的旧文件若被手改则停止，先把个人内容保存到源目录后再重建。`check` 同时检查生成物散列、源摘要和预览副本；旧文件或手改输出会失败。最终复制不是文件系统事务，中途失败仍须重建并通过检查后才使用，不支持多人并发修改。

预览服务只绑定 `127.0.0.1`，只展示指定旅程的 `site/`，用 Ctrl+C 停止。底图/CDN 需联网，PNG/GeoJSON/Markdown 可离线；不批量下载公共地图瓦片。文件路径是项目相对路径，换电脑不依赖原来的 D 盘位置。
