# -*- coding: utf-8 -*-
"""Class Widget 评测用例。

模拟时间：2026-08-05（周三）10:30，第 3 节（10:10-10:55）上课中。
"这周日" = 2026-08-09（周日）；"明天" = 2026-08-06（周四）。

档案课表（testdata/configs/schedules/课程表.json）：
  周一：语文、数学、英语、物理、历史、生物、体育与健康
  周二：数学、语文、英语、道德与法治、物理、地理、音乐
  周三：英语、数学、物理、历史、生物、体育与健康、信息技术
  周四：数学、语文、英语、物理、地理、化学、劳动技术
  周五：语文、数学、英语、体育与健康、道德与法治、美术、班会

时间表（上课节次）：
  第1节 08:00-08:45 | 第2节 08:55-09:40 | 第3节 10:10-10:55
  第4节 11:05-11:50 | 第5节(下午1) 14:00-14:45 | 第6节(下午2) 14:55-15:40
  第7节(下午3) 15:50-16:35
"""

CASES = [
    {
        "id": "swap_am3_pm1",
        "text": "上午第三节跟下午第一节换了",
        "expected": (
            "周三（2026-08-05）第3节与第5节（下午第一节）对调："
            "第3节 物理 → 生物；第5节 生物 → 物理。"
            "应调用 class-widgets__swap_classes（entry wed-p3 与 wed-p5），"
            "或等价地 replace_class / upsert_entry / update_schedule。"
            "当天临时换课即可；永久改课表也可以。"
        ),
    },
    {
        "id": "sunday_use_monday",
        "text": "这周日调休上周一的课，调一下课表",
        "expected": (
            "周日（2026-08-09）按周一课表上课："
            "语文、数学、英语、物理、历史、生物、体育与健康。"
            "应调用 class-widgets__set_reschedule_day，"
            "date=2026-08-09，weekday=1（周一）。"
        ),
    },
    {
        "id": "next_lesson",
        "text": "下节课是啥",
        "expected": (
            "当前模拟时间 10:30 处于第3节（物理），"
            "下节课是第4节（11:05-11:50）= 历史。"
            "必须以 get_runtime 返回的 now/current_time 为准，不能用系统 date。"
        ),
    },
    {
        "id": "pm1_lesson",
        "text": "下午第一节是啥",
        "expected": "周三下午第一节（第5节，14:00-14:45）= 生物。",
    },
    {
        "id": "tomorrow_this_lesson",
        "text": "明天这节是啥课",
        "expected": "明天周四（2026-08-06）同节次（第3节）= 英语。",
    },
    {
        "id": "math_period",
        "text": "今天第几节数学",
        "expected": "周三数学在第2节（08:55-09:40），答案是第2节。",
    },
    {
        "id": "cw_delay",
        "text": "调一下cw延迟，铃声慢了5秒",
        "expected": (
            "铃声滞后 5 秒需要减小时间偏移：schedule.time_offset 从 0 改为 -5。"
            "Class Widgets 设置说明：增大偏移以抵消铃声提前，减小偏移以抵消铃声滞后。"
            "应调用 class-widgets__set_setting，key=schedule.time_offset，value=-5。"
        ),
    },
    {
        "id": "cw_ui_bigger",
        "text": "cw 主界面调大一点",
        "expected": (
            "把主界面整体缩放调高：preferences.scale_factor 从默认 1.0 调大（如 1.0 → 1.2）。"
            "应调用 class-widgets__set_setting，key=preferences.scale_factor，value>1.0。"
        ),
    },
]

CASES_BY_ID = {c["id"]: c for c in CASES}
