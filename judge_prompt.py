# -*- coding: utf-8 -*-
"""裁判（deepseek）提示词构造。

把每个用例的：任务文本、标准答案、模型执行过程（思考 + 工具调用 + 最终回答）
组装为带判定规则的提示词，交给 deepseek 裁判评分。
"""

BACKDROP = """你是一名严格的软件自动化测试裁判，负责评判"AI 助教（SecAgent）通过工具操作 ClassIsland 课表软件"的任务执行质量。

## 环境背景

- ClassIsland 是课表软件；SecAgent 通过"ClassIsland 联动插件"（HTTP 服务 127.0.0.1:18789）操作它。
- 本次评测 ClassIsland 以模拟时间启动：**2026-08-05（周三）10:30**，正处于第 3 节（10:10-10:55）上课中。
- 数据档案"课程表.json"内容如下（节次按时间表顺序）：
  - 时间表：第1节 08:00-08:45；第2节 08:55-09:40；第3节 10:10-10:55；第4节 11:05-11:50；第5节（下午第一节）14:00-14:45；第6节（下午第二节）14:55-15:40；第7节（下午第三节）15:50-16:35。
  - 周一：语文、数学、英语、物理、历史、生物、体育与健康
  - 周二：数学、语文、英语、道德与法治、物理、地理、音乐
  - 周三：英语、数学、物理、历史、生物、体育与健康、信息技术
  - 周四：数学、语文、英语、物理、地理、化学/科学、劳动技术
  - 周五：语文、数学、英语、体育与健康、道德与法治、美术、班会
- "这周日" = 2026-08-09（周日）；"明天" = 2026-08-06（周四）。
- ClassIsland 主配置（Settings.json）中 TimeOffsetSeconds 当前值为 0。ClassIsland 设置页对它的说明原文："设定课程时间与实际时间的偏移值。增大偏移以抵消铃声提前，减小偏移以抵消铃声滞后。"

## 可用工具（工具名带 classisland-connector__ 前缀）

- get_classisland_schedule：查询某天课程（可指定日期，省略日期查今天）
- read_classisland_profile：按路径读档案片段（如 Profil 下 JSON 的某个节点）
- write_classisland_profile：对档案做差量更新（patch 对象递归合并；path+value 替换单字段）
- create_classisland_profile_from_timetable：按语义课表行创建新档案
- list_classisland_profiles / read_classisland_main_config / list_classisland_settings
- update_classisland_main_config：按 patch 更新主配置
- list_classisland_components / list_classisland_component_configs / read_classisland_component_config / write_classisland_component_config / update_classisland_component：主界面组件读写

## 判定方法论（重要）

对每个用例，你拿到的是：
1. 任务文本
2. 标准答案（预期结果 + 预期过程）
3. 模型的执行过程记录：思考片段（reasoning）、工具调用（含参数与返回结果）、最终回答

判定规则：
1. **结果正确性**：最终回答（或修改后的系统状态）是否与标准答案一致。修改类用例要看工具参数是否把值改对；查询类用例要看最终回答的科目/节次是否答对。
2. **过程真实性**：查询类任务必须实际调用过 get_classisland_schedule / read_classisland_profile 等工具，而不是凭记忆编造答案。修改类任务必须调用对应的写工具（write_classisland_profile / update_classisland_main_config / update_classisland_component / create_classisland_profile_from_timetable 等）且参数正确。
3. **真正改对 vs 口头答应**：如果模型说"已修改"但工具调用失败、或没有执行任何写操作、或写操作参数与用户要求不符，一律判为未真正改对。
4. **编造检测**：工具返回结果与模型最终声称不一致，或模型描述了不存在的工具返回，判为编造，过程不通过。
5. **验证动作加分**：修改后重新查询/读取确认生效，是过程正确的有力证据。
6. 超时未完成、无任何工具调用、过程文件缺失 = 直接不通过。

每个用例输出一个 JSON 对象，最终输出一个 JSON 数组：
[
  {
    "case_id": "...",
    "pass": "pass | partial | fail",
    "result_correct": true/false,
    "process_correct": true/false,
    "evidence": "引用过程记录中关键的思考/工具调用/返回片段，说明判定的依据",
    "reason": "用中文解释为什么这样判，指出与实际标准答案的偏差（如有）"
  }
]
"""


def build_case_section(case: dict) -> str:
    return (
        f"### 用例：{case['id']}\n"
        f"- 任务文本：{case['text']}\n"
        f"- 标准答案：{case['expected']}\n"
    )


def build_prompt(cases, executions: list[dict]) -> str:
    """cases: 用例定义列表；executions: 与 cases 对应的执行记录 dict 列表。"""
    sections = []
    for case, exec_info in zip(cases, executions):
        sections.append(build_case_section(case))
        sections.append("执行过程记录：\n" + exec_info["trace"])
    return BACKDROP + "\n\n## 待评判用例\n\n" + "\n".join(sections) + "\n\n请严格按上述规则评判，只输出 JSON 数组。"
