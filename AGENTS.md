# 旅行项目约定

处理目的地认知、筛选、攻略、日程或复盘时，先读 `skills/travel-workflow/SKILL.md`，再按需读引用文件。其他任务不强行套用旅行流程。

- 正式资料只读写 `travel/`：目的地知识在 `destinations/<id>/`，本次需求、筛选、日计划、决策与经历在 `trips/<id>/`。目录与唯一来源见 `docs/workflow.md` 和 `docs/data-model.md`。
- `tests/fixtures/` 是模拟输入，`tests/evidence/` 是历史验收证据，`tests/output/` 是可重建测试输出；不得作为用户已选行程或真实经历导入。空模板导出不包含它们。
- 攻略和地图是生成物。使用 `scripts/travel.py build/check --trip <id> --day <id>` 同步 `generated/` 和 `site/`；不逐个手改输出。道路缺失时先 `fetch`，不能降级为直线冒充道路。
- 新旅程允许空草稿。取消保留知识；候选意向不等于排入日程。实际经历写 `journal/`，复盘仅在用户要求时写 `reviews/`，不实时改写。
- Skill 位于项目内，未全局安装。用户已指定 `https://github.com/Shaolhhh/KK_Travel` 维护文档和项目源资料；GitHub 操作遵从当前任务授权。不要上传 `.gitignore` 排除的本机环境、临时文件、可重建输出或私人附件。
- 现有生成器验收范围为单日最多三个活动景点、酒店/机场、汽车路线或明确标注的顺序示意；费用仅 MYR 已知门票小计。多日目录不代表跨日优化已经实现；其他模式与 QGIS 仍需扩展验证。
