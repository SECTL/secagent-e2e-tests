# SecAgent × ClassIsland 自动化评测

用 pytest 驱动 SecAgent CLI 对测试版 ClassIsland（支持 `--backupZip` / `--simulateTime` 的 SecAgent 测试分支）做端到端任务评测。

## 工作原理

每个用例：
1. 生成"增强备份 zip"：把 `Backup_ForTest1.zip` 的档案文件名修复（UTF-8），并把 `ClassIsland.SecAgent.Plugin.cipx` 注入 `Plugins/classisland.secagent/`
2. 以 `ClassIsland.exe --backupZip <zip> --simulateTime 2026-08-05T10:30:00 --skip-oobe --quiet` 启动测试实例（独立临时数据目录，退出自动清理）
3. 等待联动服务 `http://127.0.0.1:18789/health` 就绪
4. 调用 SecAgent CLI：`node dist/index.js run "<任务>" --workspace ~/SecAgentWorkspace --model sectl-official:deepseek-v4-flash`（用本机客户端工作区的登录态与"快速"模型档）
5. 60 秒超时即杀掉；收集 CLI 输出 + 会话 `runtime.jsonl`（模型思考与工具调用全过程）到 `results/<case_id>/`
6. pytest 只断言执行链路成功；**对错判定交给 deepseek 裁判**（`judge.py`）

## 用例与标准答案

模拟时间 2026-08-05（周三）10:30，第 3 节上课中。档案课表（课程表.json）：
周一 语文数学英语物理历史生物体育与健康；周二 数学语文英语道德与法治物理地理音乐；
周三 英语数学物理历史生物体育与健康信息技术；周四 数学语文英语物理地理化学/科学劳动技术；
周五 语文数学英语体育与健康道德与法治美术班会。时间表：第1节 08:00 / 第2节 08:55 / 第3节 10:10 / 第4节 11:05 / 第5节(下午1) 14:00 / 第6节 14:55 / 第7节 15:50。

| id | 任务 | 标准答案 |
|----|------|----------|
| swap_am3_pm1 | 上午第三节跟下午第一节换了 | 周三第3节 物理↔第5节 生物；改后第3节生物、第5节物理 |
| sunday_use_monday | 这周日调休上周一的课，调一下课表 | 周日(08-09)课表改为周一：语文数学英语物理历史生物体育与健康 |
| next_lesson | 下节课是啥 | 第4节 历史 |
| pm1_lesson | 下午第一节是啥 | 第5节 生物 |
| tomorrow_this_lesson | 明天这节是啥课 | 周四第3节 英语 |
| math_period | 今天第几节数学 | 第2节 |
| ci_delay | 调一下ci延迟，铃声慢了5秒 | TimeOffsetSeconds 0 → -5（减小偏移抵消铃声滞后） |
| ci_ui_bigger | ci主界面调大一点 | 主界面组件字号调大（MainWindowBodyFontSize 16→≥18 等） |

## 使用

```bash
# 1. 准备（一次性）
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt

# 2. 配置（环境变量，均有默认值，见 eval_config.py）
set CLASSISLAND_EXE=D:\path\to\ClassIsland.Desktop.exe   # 必须支持新参数
set BACKUP_ZIP=D:\Dowenlod下载\Backup_ForTest1.zip

# 3. 跑全部用例（每个 60s 超时，约 8 × 1 分钟内）
.venv/Scripts/python run_eval.py
# 或
.venv/Scripts/python -m pytest test_eval.py -v

# 4. 裁判（需要用户提供 deepseek key 和端点）
set JUDGE_API_KEY=sk-xxx
set JUDGE_BASE_URL=https://api.deepseek.com/v1
set JUDGE_MODEL=deepseek-reasoner
.venv/Scripts/python judge.py
```

## 目录

- `eval_config.py` 配置（路径/模型/超时/模拟时间，均可用环境变量覆盖）
- `ci_harness.py` 增强 zip 生成、CI 实例启停、健康检查
- `run_case.py` 单用例执行与过程收集
- `eval_cases.py` 8 个用例定义与标准答案
- `test_eval.py` pytest 用例（链路断言）
- `judge_prompt.py` 裁判提示词（含标准答案 + 过程判定规则）
- `judge.py` deepseek 裁判调用
- `run_eval.py` 一键入口
- `results/<case_id>/` 每用例的 `cli_stdout.txt`、`runtime.jsonl`、`session.json`、`summary.json`
