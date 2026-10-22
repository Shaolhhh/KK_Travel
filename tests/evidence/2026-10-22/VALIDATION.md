# 正式项目模板验收 · 2026-10-22

本轮将已验证的原型整理为可复用的本地项目模板。没有初始化 Git、推送 GitHub、安装全局 Skill 或新增旅行事实检索。

## 交付结构

- `travel/destinations/kota-kinabalu/`：目的地概览、参考点 GeoJSON、三个景点知识目录、酒店和机场落脚点。沿用2026-10-21来源与核实日期，不把文件整理当作重新核实。
- `travel/trips/kk-draft/`：已确认酒店和汽车／出租车方式；三项候选，零已排景点，零取消决定。日计划是空草稿。日期、人数、预算口径与航班未知，机场 T1 仍待确认。
- `tests/fixtures/kota-kinabalu/`：固定模拟输入，包括十条有向道路缓存；与真实资料分开。
- `tests/evidence/2026-10-21/`：原静态/道路/浏览器验收证据保留。旧命令路径只作历史语境，报告导航链接已迁移。
- `tests/output/`：重新回放的模拟攻略和地图。不会写入正式 `travel/`。
- `dist/travel-project-template/` 与对应 ZIP：独立空白项目，只含工具、本地 Skill、模板、文档与空资料目录。无当前旅行资料、测试夹具、缓存、历史证据或本机依赖。

完整生命周期与目录责任见 [workflow.md](../../../docs/workflow.md)，唯一字段与运行方式见 [data-model.md](../../../docs/data-model.md)。

## 验证结果

**20 项自动测试通过**，原始输出在 [tests.txt](tests.txt)。新增或强化的覆盖包括：

1. 创建新项目不携带真实或模拟数据，已存在目标拒绝覆盖。
2. 新旅程没有默认景点、时段或模拟选择；空草稿可检查，但不能生成假行程。
3. 导出的项目入口可从项目外的工作目录运行；隔离副本的 `check` 验证实际生成结果，依赖通过测试环境提供。
4. 正式入口使用同一目录完成原始、取消、重排，攻略/路线/地图及预览副本一致；未完成的其他候选不阻塞已经明确的景点。
5. 日志、复盘和知识源不被生成器改写；篡改预览副本会被发现。
6. 汽车道路切换为示意图、移除当日引用后，过时的道路明细、落脚点视图和景点攻略被清理；知识源、日志和未被清单跟踪的笔记保留。
7. 更换酒店/机场名称和参考描述不会继续输出固定的“亚庇喜来登／BKI T1”标题。

原有缓存方向、缓存刷新保护、坐标变化失效、时间冲突、取消/重排、文件篡改、GET/HEAD 服务范围等回归也通过。

基础示意与真实道路三个场景均重新生成并检查通过，见 [schematic-replay.txt](schematic-replay.txt)、[road-replay.txt](road-replay.txt)。真实草稿检查见 [formal-draft.txt](formal-draft.txt)。回归前后对正式资料文件逐个比较 SHA-256，内容未变，见 [results.json](results.json)。本次测试没有联网获取新的道路数据。

静态地图打开检查，通用标题、道路几何、景点及酒店/机场可读。HTML 的本次改动是中性化机场提示文字，没有改变交互行为；沿用 [前一轮浏览器实测](../2026-10-21/road/VALIDATION.md)，**不声称本轮重新做了完整浏览器交互验收**。

独立只读复核发现并修复了过时生成物残留、海滩文案中模拟改期痕迹两项问题；修复后复核未发现剩余重要问题。项目本地 Skill 格式检查及模板导出检查结果见 [release-check.json](release-check.json)。

## 迁移说明

| 旧位置 | 新位置 |
|---|---|
| `demo/places` | `tests/fixtures/kota-kinabalu/places` |
| `demo/scenarios` | `tests/fixtures/kota-kinabalu/scenarios/schematic` |
| `road-demo/anchors`、`road-demo/scenarios`、`road-demo/cache` | 测试夹具的 `anchors`、`scenarios/road`、`cache` |
| `demo/evidence`、`road-demo/evidence` | `tests/evidence/2026-10-21/schematic`、`road` |
| `demo/current`、`road-demo/current`、`road-demo/site` | `tests/output/schematic`、`road`、`site` |

移动时核对文件摘要。某个旧目录不允许整体重命名，因此最后36个文件改为逐文件移动并核对，详见 [migration-files.json](migration-files.json)；没有更改系统执行策略或权限。旧 `demo/`、`road-demo/` 可能保留空目录壳，无旅行资料存于其中。

## 边界

模板目录可容纳不同目的地、多个旅程和逐日资料；现有自动生成器仍按单日工作，最多三个活动景点，费用为 MYR 已知门票小计。未新增跨日优化、换酒店衔接、自动汇率、公交/步行、实时交通或 QGIS；正式行程仍须结合日期和需求核实。没有创建实际旅行日志或复盘内容。
