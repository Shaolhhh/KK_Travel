# 旅行知识与攻略项目

这是空白正式项目，不含任何目的地、酒店、模拟行程或实际经历。先读 [全流程](docs/workflow.md) 和 [数据约定](docs/data-model.md)。本地 Skill 位于 `skills/travel-workflow/`，项目 `AGENTS.md` 指向它，未全局安装。

在此目录运行（Python 3.12+）：

```text
python -m pip install -r requirements.txt
python scripts/travel.py destination my-destination --name "目的地名称" --timezone Asia/Kuching
python scripts/travel.py trip first-trip --destination my-destination --title "旅行名称"
python scripts/travel.py inspect --trip first-trip
```

时区须按实际目的地填写。新旅程是空草稿；从 `overview.md` 建立认知，再填写需求、候选和日计划。景点模板、落脚点模板在 `skills/travel-workflow/assets/`，每景点一个稳定目录。实际日志与复盘默认不生成。

确认景点与时段、补齐知识后，将对应日计划设为 `ready`，按交通模式获取道路，再执行 `build`、`check`、`serve`（详见数据约定）。当前工具已验收单日最多三个景点、酒店/机场和汽车道路；金额字段限 MYR 门票小计，其他币种和复杂多日路线需扩展后验证。

`travel/` 是源数据，`generated/` 与 `site/` 是可重建视图；不要混入测试数据。创建本项目不会初始化 Git，也不上传或发布任何文件。
