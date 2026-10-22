# 固定测试资料

`kota-kinabalu/` 来自已通过的三景点最小验证：places、anchors、scenarios/schematic、scenarios/road、cache。场景明确为 simulation=true；酒店和道路是真实来源的测试输入，但不是已确认旅行安排。

只供测试及样例回放使用，不由正式项目命令默认读取。更新夹具属于修改测试基准；正式旅行变化只改 `travel/`。历史结果在 `tests/evidence/`，重新回放的结果在 `tests/output/`。
