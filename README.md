# 旅行知识与攻略项目模板 · v1.0

将目的地认知、景点筛选、攻略维护、旅途记录与复盘保存在同一套文件中。正式旅行资料与模拟测试分开维护，项目仓库为 [Shaolhhh/KK_Travel](https://github.com/Shaolhhh/KK_Travel)。

从 [全流程与目录](docs/workflow.md) 了解如何维护，从 [数据约定与命令](docs/data-model.md) 开始操作。当前正式草稿是 [亚庇旅程](travel/trips/kk-draft/trip.json)，先读 [亚庇认知概览](travel/destinations/kota-kinabalu/overview.md) 和 [已确认需求](travel/trips/kk-draft/requirements.md)。

| 位置 | 内容 |
|---|---|
| `travel/destinations/` | 可复用的目的地知识；每景点一个文件夹，酒店/机场单独保存 |
| `travel/trips/` | 每次旅行的需求、筛选、日计划、选择理由、实际日志与按需复盘 |
| `skills/travel-workflow/` | 本地 Skill、唯一模板源与已验证的生成器 |
| `scripts/` | 创建项目、维护资料、生成检查、道路查询、本地预览 |
| `tests/fixtures/` | 亚庇三景点的固定模拟输入，供回归测试使用 |
| `tests/evidence/` | 验收证据与迁移记录；不是用户旅行经历 |
| `tests/output/` | 可重建模拟攻略和地图，不进入真实计划 |

亚庇草稿只确认用户指定的喜来登酒店和汽车／出租车方式。三个景点迁入候选知识库，未选中、未取消、未安排时段；旅行日期、人数、票种与航班仍未知。BKI T1 作为待航班确认的参考落脚点保留。`journal/`、`reviews/` 和正式生成目录为空。

## 本地使用

使用 Python 3.12+，在项目根目录安装 `requirements.txt` 中的依赖。中文静态图需要微软雅黑或 Noto Sans CJK。下方 `python` 可替换为自己的解释器路径。

```powershell
$travelPython = 'python'
& $travelPython -m pip install -r requirements.txt
& $travelPython -X utf8 scripts/travel.py inspect --trip kk-draft
& $travelPython -X utf8 scripts/travel.py new-project ./dist/my-travel-project
```

`new-project` 创建干净的独立项目，不带当前亚庇资料、测试数据、缓存或依赖；目标存在时拒绝覆盖。新项目按导出目录内的 README 安装依赖并创建目的地与旅程，不需要 Git。`dist/` 是可重建的本地导出目录，不纳入仓库。

正式日计划补齐后，将 `status` 设为 `ready`，再执行：

```powershell
& $travelPython -X utf8 scripts/travel.py fetch --trip kk-draft --day day-01
& $travelPython -X utf8 scripts/travel.py build --trip kk-draft --day day-01
& $travelPython -X utf8 scripts/travel.py check --trip kk-draft --day day-01
& $travelPython -X utf8 scripts/travel.py serve --trip kk-draft
```

未选景点的草稿会拒绝生成，不预填假行程。`fetch` 才联网查询道路；`build/check` 使用已有缓存。预览只展示地图目录，地址为 `http://127.0.0.1:8765/`，Ctrl+C 停止。HTML 底图/CDN 需要联网，PNG/GeoJSON/Markdown 可离线阅读。

## 回归与历史结果

```powershell
& $travelPython -X utf8 -m unittest discover -s tests -v
& $travelPython -X utf8 scripts/run_demo.py
& $travelPython -X utf8 scripts/run_road_demo.py
& $travelPython -X utf8 scripts/serve_maps.py --directory tests/output/site
```

这些命令只读取 `tests/fixtures/` 并生成测试输出。模板化验收见 [本次报告](tests/evidence/2026-10-22/VALIDATION.md)；先前已完成的 [道路与浏览器验收](tests/evidence/2026-10-21/road/VALIDATION.md) 保留，历史报告中的旧路径可对照迁移记录。

仓库保存文档、旅行源资料、Skill/脚本、固定测试数据及历史验收证据。`.runtime/`、`.venv/`、`.work/`、`dist/`、`tests/output/` 和旅程中的生成物、预览副本、道路缓存、私人附件由 `.gitignore` 排除。地图 HTML 下载到本地后通过预览服务打开；GitHub 文件页本身不执行交互地图脚本。

复用 OSRM/FOSSGIS、Folium/Leaflet、OpenStreetMap、GeoJSON 与 Pillow。自定义部分是资料约定、对话变更规则、缓存适配与同步校验。当前自动制图验收范围仍是单日最多三个景点加酒店/机场，费用仅 MYR 门票小计；未新增实时交通、全程优化、公交/步行或 QGIS 能力。
